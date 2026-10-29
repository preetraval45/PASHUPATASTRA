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


def standardise(scores: np.ndarray) -> np.ndarray:
    """Per-query z-scores, so two scorers on different scales can be added.
    A column a scorer cannot rank (-inf) goes just below that row's lowest finite score."""
    s = np.array(scores, dtype=float)
    finite = np.isfinite(s)
    low = np.where(finite, s, np.inf).min(axis=1, keepdims=True)
    s = np.where(finite, s, np.where(np.isfinite(low), low - 1e-6, 0.0))
    return (s - s.mean(axis=1, keepdims=True)) / (s.std(axis=1, keepdims=True) + 1e-9)


def fuse(a: np.ndarray, b: np.ndarray, weight: float) -> np.ndarray:
    return weight * standardise(a) + (1 - weight) * standardise(b)


def choose_weight(a: np.ndarray, b: np.ndarray, gold: list[int], grid: int = 11) -> float:
    """The weight on `a` with the best MRR on these (validation) rows; ties keep the lower weight."""
    best, best_mrr = 0.0, -1.0
    for w in np.linspace(0, 1, grid):
        m = summarise(ranks(fuse(a, b, w), gold))["mrr"]
        if m > best_mrr:
            best, best_mrr = float(w), m
    return round(best, 2)


def prune(coef: np.ndarray, keep: int) -> np.ndarray:
    """Keep each row's `keep` largest-magnitude weights, zero the rest, and
    round the survivors to int8 with one scale per row, as the API would hold
    them. Returns the dequantised matrix, so it scores exactly as served."""
    out = np.zeros_like(coef, dtype=np.float64)
    for r, row in enumerate(coef):
        top = np.argpartition(-np.abs(row), keep - 1)[:keep] if keep < len(row) else np.arange(len(row))
        scale = (np.abs(row[top]).max() / 127.0) or 1.0
        out[r, top] = np.round(row[top] / scale) * scale
    return out


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)
