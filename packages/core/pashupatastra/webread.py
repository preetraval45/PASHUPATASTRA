"""Reading the open web for an answer: documents, passages, and the features that rank them.

Shared by the API, which answers with it, and by `sati.webqa`, which trains Brahmacharini's passage
ranker on the same features, so what is served is exactly what was trained. Standard library only.
"""

from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from . import trees

USER_AGENT = "pashupatastra/0.1 (+https://pashupatastra.vercel.app)"
TIMEOUT = 5
MAX_BYTES = 1_500_000

WORD = re.compile(r"[a-z0-9][a-z0-9\-]*")
STOP = frozenset(
    "a an and are as at be by can could did do does for from had has have how i in is it its of on or "
    "should so the their there they this that these those to was were what when where which who whom whose "
    "why will with would you your my me we our us explain about tell simple terms please define meaning "
    "mean means describe called known much many some any one use used work works happen happens".split()
)
DEFINITION = re.compile(
    r"^\s*(?:what|who)\s+(?:is|are|was|were)\s+(?:a |an |the )?(?P<x>[^?]{1,60}?)\s*\??\s*$", re.IGNORECASE)
FACTOID = re.compile(r"\b(of|in|by|from)\b|\w+est\b|\b(first|last|most|least|largest|biggest)\b", re.IGNORECASE)
NUMERIC = re.compile(r"\b(how (many|much|far|long|old|tall|big|fast)|population|speed|distance|temperature|"
                     r"boiling|freezing|height|when|what year|melting)\b", re.IGNORECASE)
NUMBER = re.compile(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million|billion)\b",
                    re.IGNORECASE)
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
NAME = re.compile(r"\b[A-Z][a-z]+ (?:[A-Z]\. )?[A-Z][a-z]+\b")
META = re.compile(r"^(list|outline|history|timeline|index|glossary|comparison) of\b|\(disambiguation\)", re.IGNORECASE)
REFER = re.compile(r"\b(may|can|might) refer to\b|peer-reviewed\b.{0,40}\bjournal\b", re.IGNORECASE)
WANTS_META = re.compile(r"\b(list|history|timeline|outline)\b", re.IGNORECASE)
LEADING = re.compile(r"^\s*(what|who|whom|which|when|where|why|how)(\s+(is|are|was|were|do|does|did|many|much|far|long))?"
                     r"(\s+(a|an|the))?\s+", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass(frozen=True)
class Document:
    title: str
    url: str
    text: str
    source: str
    licence: str = ""
    exact: bool = False
    """The page a source returned as titled exactly what was asked about, redirects followed."""
    rank: int = 0
    """Its place in the source's own results, from 0."""


def raw_words(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOP]


def stem(word: str) -> str:
    if len(word) <= 4 or word.endswith("ss"):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 4 else word


def words(text: str) -> list[str]:
    return [stem(w) for w in raw_words(text)]


def query_terms(question: str) -> list[str]:
    return list(dict.fromkeys(words(question)))


def subject(question: str) -> str | None:
    """What a definition question asks about ("what is DNA?" → "DNA"); None for any other question."""
    found = DEFINITION.match(question)
    if not found:
        return None
    x = found.group("x").strip()
    return x if len(x.split()) <= 4 and not FACTOID.search(x) else None


def question_phrases(question: str) -> list[str]:
    """Consecutive word pairs of the question once its wh-opening is gone, each holding at least one
    informative word: "what is the currency of Japan?" → "currency of", "of japan"."""
    tokens = WORD.findall(LEADING.sub("", question.lower()))
    return [f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False) if a not in STOP or b not in STOP]


def quality(asked: list[str], title: str, text: str) -> tuple[float, float]:
    """How much of the question a passage covers, and how exactly its title names the subject.
    Both are 0–1 and source-neutral, so a knowledge-base entry and a web page can be compared."""
    if not asked:
        return 0.0, 0.0
    body = set(words(f"{title} {text}"))
    coverage = sum(1 for w in asked if w in body) / len(asked)
    named = words(title)
    title_fit = (sum(1 for w in named if w in asked) / len(named)) if named else 0.0
    return coverage, title_fit


def get(url: str, params: dict | None = None) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"user-agent": USER_AGENT, "accept-encoding": "identity"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read(MAX_BYTES)


WIKI = "https://en.wikipedia.org/w/api.php"
WIKI_PAGE = {"prop": "extracts|info|pageprops", "inprop": "url", "exintro": 1, "explaintext": 1,
             "redirects": 1, "format": "json", "formatversion": 2}


def _wiki_pages(params: dict) -> list[Document]:
    pages = json.loads(get(WIKI, {"action": "query", **WIKI_PAGE, **params}).decode("utf-8")).get("query", {}).get("pages", [])
    exact = "titles" in params
    ordered = sorted(pages, key=lambda p: p.get("index", 0))
    return [Document(p["title"], p["fullurl"], p.get("extract", ""), "Wikipedia", "CC BY-SA 4.0", exact, i)
            for i, p in enumerate(ordered)
            if p.get("extract") and "disambiguation" not in p.get("pageprops", {})]


def _wiki_full(doc: Document) -> Document:
    """The whole article in place of its introduction; the introduction if the fetch fails."""
    try:
        params = {k: v for k, v in WIKI_PAGE.items() if k != "exintro"}  # any exintro value means true
        params |= {"titles": doc.title, "exlimit": 1, "exsectionformat": "plain"}
        pages = json.loads(get(WIKI, {"action": "query", **params}).decode("utf-8")).get("query", {}).get("pages", [])
        text = pages[0].get("extract", "") if pages else ""
    except Exception:
        return doc
    return Document(doc.title, doc.url, text[:60_000], doc.source, doc.licence, doc.exact, doc.rank) if text else doc


def wikipedia(question: str, limit: int = 6, full: int = 2) -> list[Document]:
    """Wikipedia's top articles for the question, and for a definition question the article titled
    exactly what was asked about ("what is DNA?" → DNA). The first `full` are read whole; the rest by
    their introductions."""
    search = " ".join(raw_words(question)) or question
    calls = [{"generator": "search", "gsrsearch": search, "gsrlimit": limit, "exlimit": limit}]
    named = subject(question)
    if named:
        calls.append({"titles": named[:1].upper() + named[1:], "exlimit": 1})
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        found = [d for batch in pool.map(_wiki_pages, calls) for d in batch]
    unique: dict[str, Document] = {}
    for d in found:
        if d.url not in unique or d.exact:
            unique[d.url] = d
    docs = sorted(unique.values(), key=lambda d: (not d.exact, d.rank))
    if full:
        with ThreadPoolExecutor(max_workers=full) as pool:
            docs[:full] = list(pool.map(_wiki_full, docs[:full]))
    return docs


def passages(doc: Document, span: int = 3) -> list[tuple[int, str]]:
    sentences = [s.strip() for para in doc.text.split("\n") for s in SENTENCE.split(para) if len(s.strip()) > 20]
    return [(i, " ".join(sentences[i : i + span])) for i in range(max(1, len(sentences)))][:120]


FEATURES = (
    "weighted", "coverage", "title_fit", "title_exact", "title_primary", "qualified", "definition",
    "lead", "position", "doc_rank", "wants_number", "has_number", "number_match", "has_year", "who_name",
    "meta", "refers", "phrase", "length",
)


def candidates(question: str, documents: Sequence[Document]) -> list[tuple[Document, str, dict[str, float]]]:
    """Every passage of every document with its features. idf is computed over this question's own
    candidates, so a word common to all of them (the subject itself) counts for little."""
    asked = query_terms(question)
    pool = [(doc, pos, text) for doc in documents for pos, text in passages(doc)]
    if not asked or not pool:
        return []
    named = subject(question)
    named_words = set(words(named)) if named else set()
    wants_number = bool(NUMERIC.search(question))
    wants_meta = bool(WANTS_META.search(question))
    is_who = question.lower().lstrip().startswith("who")
    phrases = question_phrases(question)
    df: dict[str, int] = {}
    for _, _, text in pool:
        for w in set(words(text)):
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log(1 + len(pool) / (1 + df.get(w, 0))) for w in asked}
    total = sum(idf.values()) or 1.0
    out = []
    for doc, pos, text in pool:
        present = set(words(text))
        coverage, title_fit = quality(asked, doc.title, text)
        exact = bool(named) and set(words(doc.title.split(" (")[0])) == named_words
        lowered = " ".join(text.lower().split())
        has_number = bool(NUMBER.search(text))
        out.append((doc, text, {
            "weighted": sum(idf[w] for w in asked if w in present) / total,
            "coverage": coverage,
            "title_fit": title_fit,
            "title_exact": float(exact),
            "title_primary": float(bool(named) and (doc.exact or (exact and "(" not in doc.title))),
            "qualified": float("(" in doc.title),
            "definition": float(bool(named)),
            "lead": float(pos == 0),
            "position": float(pos),
            "doc_rank": float(doc.rank),
            "wants_number": float(wants_number),
            "has_number": float(has_number),
            "number_match": float(wants_number and has_number),
            "has_year": float(bool(YEAR.search(text))),
            "who_name": float(is_who and bool(NAME.search(text))),
            "meta": float(not wants_meta and bool(META.search(doc.title))),
            "refers": float(bool(REFER.search(text))),
            "phrase": sum(1 for ph in phrases if ph in lowered) / len(phrases) if phrases else 0.0,
            "length": float(len(text)),
        }))
    return out


def heuristic(f: dict[str, float]) -> float:
    """The hand-set score, used until a trained ranker is exported, and the baseline it must beat."""
    if f["definition"]:
        title = 0.35 * (1.0 if f["title_primary"] else 0.6 if f["title_exact"] else f["title_fit"] * 0.5)
    else:
        title = 0.1 * f["title_fit"]
    meta = 0.3 if f["meta"] or f["refers"] else 0.0
    return (0.5 * f["weighted"] + 0.25 * f["phrase"] + title + 0.1 * f["lead"] - 0.004 * min(f["position"], 40)
            + 0.1 * f["number_match"] - meta)


def scorer(model: dict | None) -> Callable[[dict[str, float]], float]:
    if model is None:
        return heuristic
    return lambda f: trees.raw_score(model, trees.row_from(model, f))
