"""Scoring a ranked list of mitigations against the set ATT&CK links to the behaviour.

No PyTorch here, so these test anywhere. Each behaviour has several right
mitigations, so the measures are set-aware:

* **hit@1:** the first recommendation is one of the right ones.
* **recall@5:** the share of the right mitigations found in the top 5.
* **precision@5:** the share of the top 5 that are right.
* **MRR:** 1 / rank of the first right one.
* **nDCG@10:** rewards right mitigations near the top, normalised by the best
  ordering possible.
"""

from __future__ import annotations

import math

import numpy as np


def score_one(order: list[int], gold: frozenset[int]) -> dict[str, float]:
    first = next((i for i, m in enumerate(order) if m in gold), None)
    dcg = sum(1 / math.log2(i + 2) for i, m in enumerate(order[:10]) if m in gold)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(gold), 10)))
    top5 = set(order[:5])
    return {
        "hit@1": float(bool(order) and order[0] in gold),
        "recall@5": len(top5 & gold) / len(gold),
        "precision@5": len(top5 & gold) / 5,
        "mrr": 1 / (first + 1) if first is not None else 0.0,
        "ndcg@10": dcg / ideal if ideal else 0.0,
    }


def evaluate(scores: np.ndarray, golds: list[frozenset[int]]) -> dict[str, float]:
    """Mean of each measure over rows; `scores` is examples × mitigations."""
    rows = [score_one(list(np.argsort(-s, kind="stable")), g) for s, g in zip(scores, golds, strict=True)]
    out = {k: round(float(np.mean([r[k] for r in rows])), 4) for k in rows[0]} if rows else {}
    return {**out, "n": len(rows)}


def popularity(train_golds: list[frozenset[int]], size: int, rows: int) -> np.ndarray:
    """Every behaviour gets the same ranking: mitigations by training frequency."""
    counts = np.zeros(size)
    for g in train_golds:
        for m in g:
            counts[m] += 1
    return np.tile(counts, (rows, 1))


def two_hop(technique_scores: np.ndarray, technique_mitigations: list[frozenset[int]], size: int,
            k: int = 5) -> np.ndarray:
    """Behaviour → its k nearest techniques → their mitigations, each weighted by
    the technique's score."""
    out = np.zeros((technique_scores.shape[0], size))
    for i, row in enumerate(technique_scores):
        for j in np.argsort(-row)[:k]:
            for m in technique_mitigations[j]:
                out[i, m] += max(row[j], 0.0) + 1e-9
    return out
