"""Retrieval scoring and the BM25 baseline — no PyTorch, so they test anywhere."""

from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

WORD = re.compile(r"[a-z0-9][a-z0-9\-\.]*")


def ranks(scores: np.ndarray, gold: list[int]) -> list[int]:
    """1-based rank of the gold column per row."""
    order = np.argsort(-scores, axis=1)
    return [int(np.where(order[i] == g)[0][0]) + 1 for i, g in enumerate(gold)]


def summarise(r: list[int]) -> dict[str, float]:
    n = len(r)
    return {
        "recall@1": round(sum(x <= 1 for x in r) / n, 4),
        "recall@5": round(sum(x <= 5 for x in r) / n, 4),
        "recall@10": round(sum(x <= 10 for x in r) / n, 4),
        "mrr": round(sum(1 / x for x in r) / n, 4),
        "n": n,
    }


def bm25(queries: list[str], docs: list[str], k1: float = 1.5, b: float = 0.75) -> np.ndarray:
    tok = [WORD.findall(t.lower()) for t in docs]
    avg = sum(map(len, tok)) / len(tok)
    df = Counter(w for t in tok for w in set(t))
    idf = {w: math.log(1 + (len(tok) - n + 0.5) / (n + 0.5)) for w, n in df.items()}
    tfs = [Counter(t) for t in tok]
    out = np.zeros((len(queries), len(docs)))
    for i, q in enumerate(queries):
        for w in set(WORD.findall(q.lower())):
            if w not in idf:
                continue
            for j, tf in enumerate(tfs):
                f = tf.get(w)
                if f:
                    out[i, j] += idf[w] * f * (k1 + 1) / (f + k1 * (1 - b + b * len(tok[j]) / avg))
    return out
