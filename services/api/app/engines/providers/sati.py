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

from .. import techniqueclassifier
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

#: Questions asking which ATT&CK technique a behaviour is.
WHICH_TECHNIQUE = re.compile(r"\b(which|what)\b[^?]{0,60}\b(technique|ttp|att&ck)", re.IGNORECASE)

#: Below this probability a mitigation is not recommended.
RECOMMEND = 0.2

#: Which model answered, by the kind of passage the answer rests on. Brahmacharini retrieves and names
#: techniques, attack patterns and vulnerabilities; Skandamata ranks defences.
AREA_BY_KIND = {
    "technique": "brahmacharini",
    "attack pattern": "brahmacharini",
    "mitigation": "skandamata",
    "exploited vulnerability": "brahmacharini",
}

#: Words that frame a defence question rather than name its subject. Searched with them, "how do we
#: defend against ransomware?" found Antivirus first; searched without, Data Encrypted for Impact (1 Nov).
FRAMING = re.compile(
    r"\b(how|what|which|do|does|can|could|should|would|we|i|you|our|my|us|me|the|a|an|is|are|to|from|for|"
    r"against|best|ways?|way|good|steps?|it|this|that|be|of|in|on|with|about|tell|explain|please|"
    r"mitigat\w*|defend\w*|defen[cs]es?|prevent\w*|protect\w*|stop|harden\w*|block\w*|remediat\w*|"
    r"counter\w*|fix|respond|guard|secure|safe)\b|[?!.,]",
    re.IGNORECASE,
)

#: Common names for vulnerabilities the catalogue lists only by CVE and product. Expanded only when
#: the CVE is in the knowledge base, so a name never points at something it cannot cite.
ALIASES = {
    "log4shell": "CVE-2021-44228 Log4j",
    "eternalblue": "CVE-2017-0144 SMB",
    "proxylogon": "CVE-2021-26855 Exchange",
    "proxyshell": "CVE-2021-34473 Exchange",
    "printnightmare": "CVE-2021-34527 Print Spooler",
    "follina": "CVE-2022-30190 MSDT",
    "zerologon": "CVE-2020-1472 Netlogon",
    "bluekeep": "CVE-2019-0708 Remote Desktop",
    "citrix bleed": "CVE-2023-4966 Citrix",
    "heartbleed": "CVE-2014-0160 OpenSSL",
    "shellshock": "CVE-2014-6271 Bash",
    "spring4shell": "CVE-2022-22965 Spring",
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

    def technique_cosines(self, query: list[float]) -> dict[str, float]:
        """Brahmacharini's similarity to every ATT&CK technique passage: its half of the fused ranking."""
        return {p["id"]: sum(a * b for a, b in zip(query, self.vectors[i], strict=True))
                for i, p in enumerate(self.passages) if p["kind"] == "technique"}

    def technique(self, attack_id: str) -> dict | None:
        return next((p for p in self.passages if p["kind"] == "technique" and p["id"] == attack_id), None)

    def passage(self, pid: str) -> dict | None:
        if not hasattr(self, "_by_id"):
            self._by_id = {p["id"]: p for p in self.passages}
        return self._by_id.get(pid)

    def capec_mitigations(self, capec_id: str) -> list[dict]:
        """CAPEC's own mitigations for one attack pattern, filed as "CAPEC-N mitigation k"."""
        found, k = [], 1
        while (p := self.passage(f"{capec_id} mitigation {k}")) is not None:
            found.append(p)
            k += 1
        return found

    def search(self, query: list[float], k: int = 3, question: str = "") -> list[tuple[float, dict]]:
        lexical = self.bm25(question)
        # A product-specific vulnerability answers only a question that names
        # it: its CVE, or its vendor. Otherwise "a small company" finds "Cisco
        # Small Business" entries, which is word matching, not understanding.
        asked = set(terms(question))
        named_cve = bool(CVE.search(question))
        # A passage with no link cannot be cited, so it is never an answer (rule 1). Until 28 Oct the
        # export kept CAPEC's mitigations under STIX ids, titled "coa-1-0" with no link.
        lexical = {
            i: v for i, v in lexical.items()
            if self.passages[i].get("url")
            and (self.passages[i]["kind"] != "exploited vulnerability"
                 or named_cve
                 or (terms(self.passages[i]["title"])[:1] and terms(self.passages[i]["title"])[0] in asked))
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


def rank_techniques(text: str, query: list[float]) -> list[tuple[float, str]] | None:
    """Techniques ranked by Brahmacharini fused with its TF-IDF classifier, with the weight the
    validation sources chose. Served alone the encoder ranks the right technique first for 0.556
    of held-out behaviours; fused, 0.650 (brahmacharini.md). None when the classifier is not
    exported, so the caller falls back to retrieval alone."""
    if not techniqueclassifier.available():
        return None
    model = techniqueclassifier.served()
    return techniqueclassifier.fuse(knowledge().technique_cosines(query), model.probabilities(text),
                                    model.fusion_weight)


def mitigation_scores(text: str) -> dict[str, float]:
    """Each ATT&CK mitigation's probability for this behaviour. Skandamata's TF-IDF classifier when its
    export says to serve it, else Skandamata's own network. Run 40801721276 measured the pruned classifier
    at nDCG@10 0.850 against the network's 0.839 on held-out attackers (skandamata.md), so it serves."""
    if techniqueclassifier.mitigations_available():
        return techniqueclassifier.mitigations().probabilities(text)
    return {m["id"]: p for p, m in mitigator().recommend(text, k=1000)}


def expand(question: str) -> str:
    """The question with any common vulnerability name followed by its CVE and product."""
    lower = question.lower()
    extra = [cve for name, cve in ALIASES.items()
             if name in lower and knowledge().passage(cve.split()[0]) is not None]
    return f"{question} {' '.join(extra)}" if extra else question


def subject(question: str) -> str:
    """What a defence question is about, without its framing words; the question itself if nothing is left."""
    rest = " ".join(FRAMING.sub(" ", question).split())
    return rest if len(rest) >= 3 else question


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
    if out and len(out) <= limit + 40:
        return out
    # One sentence longer than the limit: cut at a word, and say it was cut.
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


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
        """Defences for what the question names. Retrieval finds the subject (searched without the
        question's framing words); ATT&CK's own links give a technique's mitigations, which Skandamata
        orders; CAPEC lists its own for an attack pattern. Skandamata alone was trained on analysts'
        write-ups and misread plain questions, so it ranks alone only when nothing else matched."""
        ranked = mitigation_scores(text)
        links = attack_links()
        about = subject(expand(text))
        hits = knowledge().search(embedder().embed(about), k=5, question=about)
        # Retrieval, not the fused ranking, picks the technique here. The fusion was measured on behaviour
        # descriptions; asked "how do we defend against ransomware encrypting our file shares?" (28 Oct) it
        # put Network Share Discovery first, where retrieval names Data Encrypted for Impact.
        names = mitigator().by_id()
        for score, hit in hits:
            if score < ANSWERABLE:
                break
            if hit.get("kind") == "technique" and hit["id"] in links:
                picks = sorted((m for m in links[hit["id"]] if m in names), key=lambda m: -ranked.get(m, 0.0))[:5]
                if picks:
                    lines = [f"To defend against {hit['title']} ({hit['id']}), most relevant first:", ""]
                    lines += [self._defence(m, names[m]["name"]) for m in picks]
                    lines += ["", f"What it is: {first_sentences(hit['text'], 220)}"]
                    urls = [hit.get("url", "")] + [names[m]["url"] for m in picks]
                    return lines + ["", "Sources: " + " · ".join(u for u in urls if u)]
            if hit.get("kind") == "attack pattern":
                own = knowledge().capec_mitigations(hit["id"])[:5]
                if own:
                    lines = [f"To defend against {hit['title']} ({hit['id']}):", ""]
                    lines += [f"- {first_sentences(m['text'], 200)}" for m in own]
                    lines += ["", f"What it is: {first_sentences(hit['text'], 220)}"]
                    return lines + ["", f"Sources: {hit['url']}"]
        picks = [(p, names[m]) for m, p in sorted(ranked.items(), key=lambda kv: -kv[1])[:5]
                 if p >= RECOMMEND and m in names]
        if not picks:
            return None
        lines = ["The defences that fit what you describe, most relevant first:", ""]
        lines += [self._defence(m["id"], m["name"]) for _, m in picks]
        return lines + ["", "Sources: " + " · ".join(m["url"] for _, m in picks)]

    @staticmethod
    def _defence(mid: str, name: str) -> str:
        """One defence as a list line: its name, then what it means in a sentence."""
        passage = knowledge().passage(mid)
        gist = first_sentences(passage["text"], 170) if passage else ""
        return f"- **{name}** ({mid})" + (f": {gist}" if gist else "")

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
                "answer": "I won't help build attacks against systems you don't own. I can explain how an attack "
                "works and how to detect and defend against it: ask that way and I will.",
                "topic": "security",
                "area": "skandamata",
                "declined": True,
            }
        if self._wants_mitigations(question):
            lines = self._mitigation_lines(question)
            if lines:
                return {
                    "answer": "\n".join([*lines[:-1], "These are recommendations: applying one is a person's decision.",
                                         "", lines[-1]]),
                    "topic": "security",
                    "area": "skandamata",
                    "declined": False,
                }
            if self.mode == "skandamata":
                return {
                    "answer": "No defence stands out for that yet. Describe the attacker behaviour you saw (what "
                    "was run, accessed or changed) and I will rank the defences against it.",
                    "topic": "security",
                    "area": "skandamata",
                    "declined": False,
                }
        question = expand(question)
        query = embedder().embed(question)
        hits = knowledge().search(query, k=3, question=question)
        if self.mode != "skandamata" and WHICH_TECHNIQUE.search(question):
            named = self._which_technique(question, query, hits)
            if named:
                return named
        if self.mode == "kushmanda" and hits and hits[0][0] >= ANSWERABLE:
            written = self._write(question, [p for _, p in hits])
            if written:
                return written
        if not hits or hits[0][0] < ANSWERABLE:
            return {
                "answer": "I answer cyber security questions, and I couldn't find one in that. Ask me how an "
                "attack works, which ATT&CK technique a behaviour is, how to defend against something, or "
                "what to do about a vulnerability. For example:\n\n- What is credential stuffing?\n"
                "- How do we defend against ransomware?\n- What should we do about Log4Shell?",
                "topic": "general",
                "area": "brahmacharini",
                "declined": False,
            }
        # A passage titled exactly what was asked about beats a near neighbour: "what is SQL injection?"
        # ranked Blind SQL Injection first (1 Nov).
        asked = subject(question).lower()
        exact = next((h for h in hits if h[0] >= ANSWERABLE and h[1]["title"].lower() == asked), None)
        if exact is None and asked != question.lower():
            wider = knowledge().search(embedder().embed(asked), k=5, question=asked)
            exact = next((h for h in wider if h[0] >= ANSWERABLE and h[1]["title"].lower() == asked), None)
        if exact is not None:
            hits = [exact] + [h for h in hits if h[1]["id"] != exact[1]["id"]]
        score, best = hits[0]
        lines = [f"**{best['title']}** ({best['id']})", "", first_sentences(best["text"], 520)]
        # The answer goes on to what to do, so one question gets the explanation and the defence:
        # Brahmacharini found the subject, ATT&CK or CAPEC names the defences, Skandamata orders them.
        sources = [best.get("url", "")]
        if self.mode == "auto" and best["kind"] == "technique" and best["id"] in attack_links():
            # Ordered as for "how do we defend against it?": asked that way, the ranking put User Training
            # first for phishing; asked "what is phishing?", Software Configuration (1 Nov).
            names, ranked = mitigator().by_id(), mitigation_scores(f"How do we defend against {best['title'].lower()}?")
            picks = sorted((m for m in attack_links()[best["id"]] if m in names), key=lambda m: -ranked.get(m, 0.0))[:3]
            if picks:
                lines += ["", "How to defend against it:", ""] + [self._defence(m, names[m]["name"]) for m in picks]
                sources += [names[m]["url"] for m in picks]
        elif self.mode == "auto" and best["kind"] == "attack pattern":
            own = knowledge().capec_mitigations(best["id"])[:3]
            if own:
                lines += ["", "How to defend against it:", ""] + [f"- {first_sentences(m['text'], 200)}" for m in own]
        related = [p for s, p in hits[1:] if s >= ANSWERABLE and p["id"] != best["id"] and p["kind"] != "mitigation"]
        if related:
            lines += ["", "Related: " + "; ".join(f"{p['title']} ({p['id']})" for p in related) + "."]
            sources += [p.get("url", "") for p in related]
        seen: list[str] = []
        for u in sources:
            if u and u not in seen:
                seen.append(u)
        lines += ["", "Sources: " + " · ".join(seen)]
        return {
            "answer": "\n".join(lines).strip(),
            "topic": "security",
            "area": AREA_BY_KIND.get(best["kind"], "brahmacharini"),
            "declined": False,
        }

    def _which_technique(self, question: str, query: list[float], hits: list[tuple[float, dict]]) -> dict | None:
        """Answers "which technique is this?" from the fused ranking, the three most likely first.
        Only when retrieval finds the question is about an ATT&CK technique at all."""
        if not any(s >= ANSWERABLE and p.get("kind") == "technique" for s, p in hits):
            return None
        ranked = rank_techniques(question, query)
        if not ranked:
            return None
        picks = [p for p in (knowledge().technique(t) for _, t in ranked[:3]) if p]
        if not picks:
            return None
        lines = ["Most likely first:", ""]
        lines += [f"{i}. {p['title']} ({p['id']})" for i, p in enumerate(picks, 1)]
        lines += ["", first_sentences(picks[0]["text"]), "",
                  "Check the first against what you observed: on attackers never seen in training it is right "
                  "about two times in three.",
                  "", "Sources: " + " · ".join(p["url"] for p in picks if p.get("url"))]
        return {"answer": "\n".join(lines), "topic": "security", "area": "brahmacharini", "declined": False}

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
                "answer": "None of the closest sources answers this, so I won't guess. Try asking it another way, "
                "or name the technique, attack or CVE.",
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
