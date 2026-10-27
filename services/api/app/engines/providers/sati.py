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

#: Questions about defending, which Skandamata answers.
MITIGATE = re.compile(
    r"\b(mitigat\w*|defend\w*|defen[cs]e|prevent\w*|protect\w*|stop|harden\w*|block\w*|remediat\w*|"
    r"counter\w*|how (do|can|should) (i|we) (fix|respond))\b",
    re.IGNORECASE,
)

#: Below this probability a mitigation is not recommended.
RECOMMEND = 0.2

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


class Skandamata:
    """The served mitigation recommender: hashed n-grams → mean of int8 rows →
    ReLU layer → one probability per ATT&CK mitigation. The export checked that
    this ranks as the trained PyTorch model does (`sati.respond.export`)."""

    def __init__(self, folder: Path = MODELS) -> None:
        self.meta = json.loads((folder / "skandamata.json").read_text(encoding="utf-8"))
        self.bag = (folder / "skandamata.bag").read_bytes()

    def recommend(self, text: str, k: int = 5) -> list[tuple[float, dict]]:
        meta, width = self.meta, self.meta["width"]
        words = WORD.findall(text.lower())
        grams = words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]
        ids = [zlib.crc32(g.encode()) % meta["buckets"] for g in grams] or [0]
        pooled = [0.0] * width
        for i in ids:
            s = meta["bag_scale"][i]
            for j, v in enumerate(array("b", self.bag[i * width : (i + 1) * width])):
                pooled[j] += v * s
        pooled = [x / len(ids) for x in pooled]
        hidden = [max(0.0, sum(w * x for w, x in zip(r, pooled, strict=True)) + b)
                  for r, b in zip(meta["w1"], meta["b1"], strict=True)]
        logits = [sum(w * h for w, h in zip(r, hidden, strict=True)) + b for r, b in zip(meta["w2"], meta["b2"], strict=True)]
        probs = [1 / (1 + math.exp(-z)) for z in logits]
        ranked = sorted(range(len(probs)), key=lambda j: -probs[j])[:k]
        return [(probs[j], meta["mitigations"][j]) for j in ranked]

    def by_id(self) -> dict[str, dict]:
        return {m["id"]: m for m in self.meta["mitigations"]}


@lru_cache
def attack_links() -> dict[str, list[str]]:
    """ATT&CK's technique → mitigation links (`sati.serving.attackmap`); empty if not exported."""
    path = MODELS / "attack_mitigations.json"
    return json.loads(path.read_text(encoding="utf-8"))["links"] if path.exists() else {}


#: Identifiers Kushmanda may write only if the passage it cites contains them.
IDENTIFIER = re.compile(r"\b(T\d{4}(?:\.\d{3})?|CVE-\d{4}-\d{4,}|CWE-\d+|M1\d{3}|CAPEC-\d+)\b")
CITED = re.compile(r"\[(\d)\]\s*$")
KUSHMANDA_ABSTAIN = "the context does not answer this"


def kushmanda_folder() -> Path:
    return MODELS / "kushmanda"


def kushmanda_available() -> bool:
    """Its weights are private: present only in a deployed archive, fetched at deploy time."""
    folder = kushmanda_folder()
    return (folder / "kushmanda.json").exists() and (folder / "tokenizer.json").exists()


@lru_cache
def writer():
    """Kushmanda's numpy engine and its tokenizer, loaded once per process."""
    from tokenizers import Tokenizer

    from ..lmengine import Engine

    folder = kushmanda_folder()
    return Engine.load(folder), Tokenizer.from_file(str(folder / "tokenizer.json"))


def skandamata_available(folder: Path | None = None) -> bool:
    folder = folder or MODELS
    return (folder / "skandamata.json").exists() and (folder / "skandamata.bag").exists()


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
def mitigator() -> Skandamata:
    return Skandamata()


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

    #: "auto" picks the model for each question; a model's name uses only that model.
    MODES = ("auto", "brahmacharini", "skandamata", "kushmanda")

    def __init__(self, mode: str = "auto") -> None:
        if mode not in self.MODES:
            raise ValueError(f"unknown Sati model {mode!r}")
        self.mode = mode
        if mode == "skandamata":
            self.model = "sati-skandamata-serve-v0"
        if mode == "kushmanda":
            self.model = "sati-kushmanda"

    def available(self) -> bool:
        if self.mode == "skandamata":
            return skandamata_available()
        if self.mode == "kushmanda":
            return kushmanda_available() and (MODELS / "knowledge.json").exists()
        return (MODELS / "brahmacharini.json").exists() and (MODELS / "knowledge.json").exists()

    def _wants_mitigations(self, question: str) -> bool:
        if self.mode == "brahmacharini" or not skandamata_available():
            return False
        return self.mode == "skandamata" or bool(MITIGATE.search(question))

    def _mitigation_lines(self, text: str) -> list[str] | None:
        """Brahmacharini finds the technique; ATT&CK's own links give its
        mitigations; Skandamata orders them. Skandamata alone was trained on
        analysts' write-ups and misread plain questions ("ransomware encrypting
        our file shares" → one wrong mitigation), while retrieval reads them well.
        With no confident technique, Skandamata ranks alone, as before."""
        ranked = {m["id"]: p for p, m in mitigator().recommend(text, k=1000)}
        links = attack_links()
        hits = knowledge().search(embedder().embed(text), k=3, question=text) if links else []
        technique = next((p for s, p in hits if s >= ANSWERABLE and p.get("kind") == "technique"
                          and p["id"] in links), None)
        if technique is not None:
            names = mitigator().by_id()
            picks = sorted((m for m in links[technique["id"]] if m in names), key=lambda m: -ranked.get(m, 0.0))[:5]
            if picks:
                lines = [f"For {technique['title']} ({technique['id']}), which this matches, ATT&CK lists these "
                         "defences, most relevant first:", ""]
                lines += [f"- {names[m]['name']} ({m})" for m in picks]
                urls = [technique.get("url", "")] + [names[m]["url"] for m in picks]
                return lines + ["", "Sources: " + " · ".join(u for u in urls if u)]
        picks = [(p, m) for p, m in mitigator().recommend(text, k=5) if p >= RECOMMEND]
        if not picks:
            return None
        lines = ["The ATT&CK mitigations Skandamata ranks highest for what you describe (its confidence in "
                 "brackets):", ""] + [f"- {m['name']} ({m['id']}) — {p:.0%}" for p, m in picks]
        return lines + ["", "Sources: " + " · ".join(m["url"] for _, m in picks)]

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
        if self._wants_mitigations(question):
            lines = self._mitigation_lines(question)
            if lines:
                return {
                    "answer": "\n".join([*lines, "", "These are recommendations. Applying any of them is a decision "
                                         "for a person, and Dharma authorises every action."]),
                    "topic": "security",
                    "area": "skandamata",
                    "declined": False,
                }
            if self.mode == "skandamata":
                return {
                    "answer": "Skandamata found no ATT&CK mitigation it is confident about for that. Describe "
                    "the attacker behaviour you saw (what was run, accessed or changed), and it will rank "
                    "the mitigations that defend against it.",
                    "topic": "security",
                    "area": "skandamata",
                    "declined": False,
                }
        hits = knowledge().search(embedder().embed(question), k=3, question=question)
        if self.mode == "kushmanda" and hits and hits[0][0] >= ANSWERABLE:
            written = self._write(question, [p for _, p in hits])
            if written:
                return written
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

    def _write(self, question: str, passages: list[dict]) -> dict[str, Any] | None:
        """Kushmanda answers in its own words from the passages Brahmacharini
        retrieved, in the chat template it was tuned on, and cites one.

        Measured weakness: it copies identifiers badly (models/kushmanda.md). So
        every identifier it writes must appear in the passage it cites; if not,
        this returns None and the retrieved passage is shown instead (rule 1)."""
        lines = [f"{p['id']} {p['title']}: {first_sentences(p['text'], 450)}" for p in passages]
        numbered = "\n".join(f"[{i}] {line}" for i, line in enumerate(lines, 1))
        prompt = f"<|user|> Context:\n{numbered}\nQuestion: {question}\n<|assistant|> "
        engine, tok = writer()
        out = engine.generate(tok.encode(prompt).ids, 96, stop=tok.token_to_id("<|end|>"))
        text = tok.decode(out).replace("<|end|>", "").strip()
        cite = CITED.search(text)
        body = CITED.sub("", text).strip()
        if not body:
            return None
        if body.rstrip(".").lower() == KUSHMANDA_ABSTAIN:
            return {
                "answer": "Kushmanda read the closest passages in Sati's knowledge and found that none of them "
                "answers this. It declines rather than guess.",
                "topic": "security", "area": "kushmanda", "declined": False,
            }
        index = int(cite.group(1)) - 1 if cite else None
        if index is None or not 0 <= index < len(passages):
            return None  # an answer must cite a passage it was given
        source = passages[index]
        if any(found not in lines[index] for found in IDENTIFIER.findall(body)):
            return None  # an identifier its cited passage does not contain
        return {
            "answer": f"{body}\n\nSource: {source['title']} ({source['source']} {source['id']}) {source.get('url', '')}".strip(),
            "topic": "security", "area": "kushmanda", "declined": False,
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
        if self._wants_mitigations(question):
            # Skandamata reads the incident's own account of what the attacker did.
            basis = by("hypothesis")[:1] + by("causal_chain")
            lines = self._mitigation_lines(" ".join(e.content for e in basis)) if basis else None
            if lines:
                return {
                    "answer": "\n".join(["From this incident's evidence:", "", *lines, "",
                                         "Recommendations only: a human authorises any change."]),
                    "evidence_refs": [e.ref for e in basis],
                    "answerable": True,
                    "proposed_action_id": None,
                    "considered": [],
                }
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
