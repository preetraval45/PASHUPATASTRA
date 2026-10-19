"""Cleaning and deduplication for Kushmanda's corpus.

What a small language model learns is dominated by what it sees most, so a
paragraph that appears forty times teaches forty times as hard — and, worse,
a duplicate that lands on both sides of the train/held-out split makes the
held-out score a memory test. Three passes:

1. **Normalise:** Unicode NFKC, markdown links reduced to their text, ATT&CK
   `(Citation: …)` markers and HTML removed, whitespace collapsed.
2. **Filter:** too short to teach anything, or mostly non-letters (tables of
   identifiers, hex dumps).
3. **Deduplicate:** exact (by content hash), then **near-duplicate** by MinHash
   over word 5-shingles with banded locality-sensitive hashing — documents
   whose estimated Jaccard similarity is at or above the threshold keep only
   their first copy.

Pure Python and deterministic: the same corpus always cleans to the same
result, which the reported numbers depend on.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import zlib

LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
CITATION = re.compile(r"\(Citation: [^)]*\)")
HTML = re.compile(r"<[^>]+>")
SPACE = re.compile(r"[ \t ]+")
WORD = re.compile(r"\w+", re.UNICODE)

MIN_CHARS = 80
MIN_LETTER_SHARE = 0.55
SHINGLE = 5
PERMUTATIONS = 64
BANDS = 16  # 16 bands x 4 rows ~ catches pairs with Jaccard >= ~0.7
THRESHOLD = 0.8
_PRIME = (1 << 61) - 1


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = LINK.sub(r"\1", text)
    text = CITATION.sub("", text)
    text = HTML.sub(" ", text)
    lines = [SPACE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def keep(text: str) -> bool:
    if len(text) < MIN_CHARS:
        return False
    letters = sum(ch.isalpha() for ch in text)
    return letters / max(1, len(text)) >= MIN_LETTER_SHARE


def _shingles(text: str) -> set[int]:
    words = WORD.findall(text.lower())
    if len(words) < SHINGLE:
        return {zlib.crc32(" ".join(words).encode())}
    return {zlib.crc32(" ".join(words[i : i + SHINGLE]).encode()) for i in range(len(words) - SHINGLE + 1)}


def _coefficients() -> list[tuple[int, int]]:
    out = []
    for i in range(PERMUTATIONS):
        h = hashlib.sha256(f"kushmanda-minhash-{i}".encode()).digest()
        out.append((int.from_bytes(h[:8], "big") % _PRIME or 1, int.from_bytes(h[8:16], "big") % _PRIME))
    return out


_COEF = _coefficients()


def signature(text: str) -> tuple[int, ...]:
    shingles = _shingles(text)
    return tuple(min((a * s + b) % _PRIME for s in shingles) for a, b in _COEF)


def jaccard_estimate(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    return sum(x == y for x, y in zip(a, b, strict=True)) / len(a)


def deduplicate(docs: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Keep the first of each exact or near-duplicate group. Returns the kept
    documents and how many were dropped at each stage."""
    stats = {"input": len(docs), "filtered": 0, "exact_duplicates": 0, "near_duplicates": 0}
    seen_hash: set[str] = set()
    buckets: dict[tuple[int, tuple[int, ...]], list[int]] = {}
    kept: list[dict] = []
    signatures: list[tuple[int, ...]] = []
    rows = PERMUTATIONS // BANDS
    for doc in docs:
        text = normalise(doc["text"])
        if not keep(text):
            stats["filtered"] += 1
            continue
        digest = hashlib.sha256(text.lower().encode()).hexdigest()
        if digest in seen_hash:
            stats["exact_duplicates"] += 1
            continue
        sig = signature(text)
        candidates = set()
        for band in range(BANDS):
            key = (band, sig[band * rows : (band + 1) * rows])
            candidates.update(buckets.get(key, ()))
        if any(jaccard_estimate(sig, signatures[c]) >= THRESHOLD for c in candidates):
            stats["near_duplicates"] += 1
            continue
        index = len(kept)
        for band in range(BANDS):
            buckets.setdefault((band, sig[band * rows : (band + 1) * rows]), []).append(index)
        seen_hash.add(digest)
        signatures.append(sig)
        kept.append({**doc, "text": text})
    stats["kept"] = len(kept)
    return kept, stats
