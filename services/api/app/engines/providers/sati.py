"""The `sati` provider — Sati AI answering from the project's own models only.

The owner's decision (18 October 2026): no external LLM answers a user. Until
Kushmanda, Sati's own language model, has been trained and taught the answer
schema, answers are composed by this provider from two things it owns:

* **Brahmacharini** (adr/SatiEmbed) — the project's own embedding model, served
  here in pure Python from int8 weights exported by `sati.embed.export`. It
  decides which stored evidence, or which knowledge-base passage, a question is
  about.
* **Deterministic composition** — the answer is built from that evidence and
  cites it, so it can never say more than the evidence does (rule 1).

It is a Gateway provider like any other (rule 5): it returns objects that
validate against the same schemas (rule 4), and every answer records
`provider: sati`. What it cannot do is write free prose beyond its evidence;
when a question goes past what it knows, it says so instead of inventing.
"""

from __future__ import annotations

import json
import math
import re
import struct
import zlib
from array import array
from functools import lru_cache
from pathlib import Path
from typing import Any

from pashupatastra.gateway import ModelRequest, SchemaViolation, Usage

from .echo import EchoProvider
from .schemas import schema_for

MODELS = Path(__file__).resolve().parents[2] / "sati_models"
WORD = re.compile(r"[a-z0-9][a-z0-9\-\.]*")
CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)

#: Below this cosine, a piece of incident evidence is not about the question.
RELEVANT = 0.28

#: Below this hybrid score (keyword + meaning, 0–1), a knowledge-base passage
#: is not an answer to the question.
ANSWERABLE = 0.55

#: Requests the general mode declines — explaining attacks is fine; building
#: working ones against others is not.
HARMFUL = re.compile(
    r"\b(write|build|create|make|code|generate)\b.{0,40}\b(malware|ransomware|keylogger|virus|worm|exploit|botnet)\b"
    r"|\bhack (into|someone|my ex|a)\b|\bsteal (passwords|credentials|accounts)\b",
    re.IGNORECASE,
)

AREA_BY_KIND = {
    "technique": "katyayani",
    "attack pattern": "katyayani",
    "mitigation": "skandamata",
    "exploited vulnerability": "chandraghanta",
}


class Brahmacharini:
    """The served embedder: hashed n-grams → mean of int8 rows → projection."""

    def __init__(self, folder: Path = MODELS) -> None:
        meta = json.loads((folder / "brahmacharini.json").read_text(encoding="utf-8"))
        self.buckets, self.width, self.dim = meta["buckets"], meta["width"], meta["dim"]
        self.scale = meta["bag_scale"]
        self.projection = meta["projection"]
        self.bias = meta["bias"]
        self.bag = (folder / "brahmacharini.bag").read_bytes()

    def _row(self, index: int) -> array:
        return array("b", self.bag[index * self.width : (index + 1) * self.width])

    def embed(self, text: str) -> list[float]:
        words = WORD.findall(text.lower())
        grams = words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]
        ids = [zlib.crc32(g.encode()) % self.buckets for g in grams] or [0]
        pooled = [0.0] * self.width
        for i in ids:
            s = self.scale[i]
            for j, v in enumerate(self._row(i)):
                pooled[j] += v * s
        n = len(ids)
        pooled = [x / n for x in pooled]
        out = [sum(w * x for w, x in zip(row, pooled, strict=True)) + b for row, b in zip(self.projection, self.bias, strict=True)]
        norm = math.sqrt(sum(x * x for x in out)) or 1.0
        return [x / norm for x in out]


STOP = frozenset(
    "a an and are as at be by can do does for from how i in is it of on or should the to was what when "
    "where which who why with you your my me we our this that these those explain about tell simple terms".split()
)


def terms(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 1]


class Knowledge:
    """The permissively licensed knowledge base: BM25 index plus embeddings.

    **Hybrid retrieval.** Brahmacharini's embedding alone is fooled by "hub"
    passages that sit close to everything, and by short questions unlike the
    behaviour text it was trained on — "what is the capital of France?" scored
    0.70 against a vulnerability entry. So a passage is a candidate only if it
    shares an informative word with the question (BM25 > 0); candidates are
    then ranked by keyword score and embedding similarity together. A question
    with no lexical foothold in the knowledge base gets no answer, which is the
    honest result.
    """

    K1, B = 1.5, 0.75
    LEXICAL, SEMANTIC = 0.65, 0.35

    def __init__(self, folder: Path = MODELS) -> None:
        self.passages = json.loads((folder / "knowledge.json").read_text(encoding="utf-8"))
        raw = (folder / "knowledge.vec").read_bytes()
        count, dim = struct.unpack_from("<II", raw, 0)
        scales = struct.unpack_from(f"<{count}f", raw, 8)
        body = raw[8 + 4 * count :]
        self.vectors = [
            [v * scales[i] for v in array("b", body[i * dim : (i + 1) * dim])] for i in range(count)
        ]
        # Titles count twice: "Credential Stuffing" should beat a passage that
        # merely mentions credentials.
        self.postings: dict[str, dict[int, int]] = {}
        self.lengths: list[int] = []
        for i, p in enumerate(self.passages):
            words = terms(f"{p['id']} {p['id']} {p['title']} {p['title']} {p['text']}")
            self.lengths.append(len(words))
            for w in words:
                self.postings.setdefault(w, {}).setdefault(i, 0)
                self.postings[w][i] += 1
        self.average = sum(self.lengths) / max(1, len(self.lengths))

    def bm25(self, question: str) -> dict[int, float]:
        n = len(self.passages)
        scores: dict[int, float] = {}
        for w in set(terms(question)):
            docs = self.postings.get(w)
            if not docs:
                continue
            idf = math.log(1 + (n - len(docs) + 0.5) / (len(docs) + 0.5))
            for i, tf in docs.items():
                norm = tf * (self.K1 + 1) / (tf + self.K1 * (1 - self.B + self.B * self.lengths[i] / self.average))
                scores[i] = scores.get(i, 0.0) + idf * norm
        return scores

    def search(self, query: list[float], k: int = 3, question: str = "") -> list[tuple[float, dict]]:
        lexical = self.bm25(question)
        # A product-specific vulnerability answers only a question that names
        # it: its CVE, or its vendor. Otherwise "a small company" finds "Cisco
        # Small Business" entries, which is word matching, not understanding.
        asked = set(terms(question))
        named_cve = bool(CVE.search(question))
        lexical = {
            i: v for i, v in lexical.items()
            if self.passages[i]["kind"] != "exploited vulnerability"
            or named_cve
            or (terms(self.passages[i]["title"])[:1] and terms(self.passages[i]["title"])[0] in asked)
        }
        if not lexical:
            return []
        top = max(lexical.values())
        scored = []
        for i, lex in lexical.items():
            cos = max(0.0, sum(a * b for a, b in zip(query, self.vectors[i], strict=True)))
            scored.append((self.LEXICAL * lex / top + self.SEMANTIC * cos, i))
        scored.sort(reverse=True)
        return [(round(score, 4), self.passages[i]) for score, i in scored[:k]]


@lru_cache
def embedder() -> Brahmacharini:
    return Brahmacharini()


@lru_cache
def knowledge() -> Knowledge:
    return Knowledge()


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def first_sentences(text: str, limit: int = 320) -> str:
    # Markup must never reach a reader: CAPEC's XHTML did, on 26 Oct 2026.
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    out = ""
    for s in sentences:
        if len(out) + len(s) > limit and out:
            break
        out = f"{out} {s}".strip()
    return out or text[:limit]


class SatiProvider:
    """Answers from Sati's own models; falls back to the stub's empty objects
    for purposes it does not serve, rather than inventing them."""

    name = "sati"
    model = "sati-brahmacharini-serve-v0"
    supports_tools = False
    structured_evidence = True

    def available(self) -> bool:
        return (MODELS / "brahmacharini.json").exists() and (MODELS / "knowledge.json").exists()

    def complete(self, prompt: str, request: ModelRequest) -> tuple[dict[str, Any], Usage]:
        if request.schema_name == "general_answer_v1":
            output = self._general(request)
        elif request.schema_name == "chat_answer_v1":
            output = self._incident(request)
        else:
            return EchoProvider().complete(prompt, request)
        missing = [k for k in schema_for(request.schema_name).get("required", []) if k not in output]
        if missing:
            raise SchemaViolation(f"sati provider omitted {missing}")
        return output, Usage()

    # --- general questions -------------------------------------------------

    def _general(self, request: ModelRequest) -> dict[str, Any]:
        question = next((e.content for e in request.evidence if e.ref == "visitor"), "")
        if HARMFUL.search(question):
            return {
                "answer": "Sati won't help build attacks against systems you don't own. It can explain how an "
                "attack works and how to detect and defend against it — ask that way and it will.",
                "topic": "security",
                "area": "skandamata",
                "declined": True,
            }
        hits = knowledge().search(embedder().embed(question), k=3, question=question)
        if not hits or hits[0][0] < ANSWERABLE:
            return {
                "answer": "That is outside what Sati's own models know so far. Today they know MITRE ATT&CK "
                "techniques and mitigations, CAPEC attack patterns and the CISA catalogue of exploited "
                "vulnerabilities. Broader questions will be answered once Kushmanda, Sati's own language "
                "model, has been trained — rather than borrowing someone else's model meanwhile.",
                "topic": "general",
                "area": "brahmacharini",
                "declined": False,
            }
        score, best = hits[0]
        lines = [
            f"The closest match in Sati's knowledge is {best['title']} ({best['source']} {best['id']}).",
            "",
            first_sentences(best["text"]),
        ]
        related = [p for s, p in hits[1:] if s >= ANSWERABLE]
        if related:
            lines += ["", "Related: " + "; ".join(f"{p['title']} ({p['id']})" for p in related) + "."]
        lines += ["", "Sources: " + " · ".join(p["url"] for _, p in hits if p.get("url"))]
        return {
            "answer": "\n".join(lines).strip(),
            "topic": "security",
            "area": AREA_BY_KIND.get(best["kind"], "brahmacharini"),
            "declined": False,
        }

    # --- questions about one incident --------------------------------------

    def _incident(self, request: ModelRequest) -> dict[str, Any]:
        question = next((e.content for e in request.evidence if e.ref == "visitor"), "").strip()
        items = [e for e in request.evidence if e.ref != "visitor"]
        q = question.lower()

        def by(source: str):
            return [e for e in items if e.source == source]

        def gist(e) -> str:
            return first_sentences(" ".join(e.content.split()), 240)

        chosen: list = []
        if q.startswith("what happened"):
            chosen = by("incident")[:1] + by("causal_chain")
            lead = "From the stored evidence, in order:"
        elif q.startswith("how do we know"):
            chosen = by("hypothesis")[:1] + [e for e in items if e.source not in ("incident", "causal_chain", "hypothesis", "plan")][:4]
            lead = "The diagnosis and the evidence it rests on:"
        elif q.startswith("what is the blast radius"):
            chosen = by("incident")[:1]
            lead = "The recorded impact:"
        elif q.startswith("what should we do first"):
            chosen = by("plan")
            lead = "The plan on file, in order — Sati proposes, and a human authorises each step:"
        if not chosen:
            vector = embedder().embed(question)
            ranked = sorted(((cosine(vector, embedder().embed(e.content[:600])), e) for e in items), key=lambda x: -x[0])
            chosen = [e for s, e in ranked[:3] if s >= RELEVANT * 0.8]
            lead = "The stored evidence most relevant to your question:"
        if not chosen:
            return {
                "answer": "The stored evidence for this incident doesn't speak to that question, and Sati "
                "answers only from evidence.",
                "evidence_refs": [],
                "answerable": False,
                "proposed_action_id": None,
                "considered": [],
            }
        body = "\n".join(f"{i}. {gist(e)}" for i, e in enumerate(chosen, start=1))
        return {
            "answer": f"{lead}\n{body}",
            "evidence_refs": [e.ref for e in chosen],
            "answerable": True,
            "proposed_action_id": None,
            "considered": [],
        }
