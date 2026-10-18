"""Scoring a root-cause ranking — the RCAEval conventions, with intervals.

`AC@k` is the share of incidents whose true root cause is in the top k;
`Avg@5` is the mean of AC@1…AC@5, RCAEval's headline number. Every share comes
with a Wilson 95% interval, because at a few hundred incidents per split the
difference between two models is often inside the noise, and a table without
intervals invites reading it as if it were not.
"""

from __future__ import annotations

import math
from collections.abc import Iterable


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion. (0, 0) for n == 0."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def score(ranks: Iterable[int | None]) -> dict[str, object]:
    """`ranks` holds the 1-based position of the true root cause per incident,
    or None when it was not among the candidates at all (counted as a miss)."""
    ranks = list(ranks)
    n = len(ranks)
    out: dict[str, object] = {"n": n}
    acs = []
    for k in (1, 2, 3, 4, 5):
        hits = sum(1 for r in ranks if r is not None and r <= k)
        ac = hits / n if n else 0.0
        acs.append(ac)
        if k in (1, 3, 5):
            low, high = wilson(hits, n)
            out[f"ac@{k}"] = round(ac, 4)
            out[f"ac@{k}_ci"] = [round(low, 4), round(high, 4)]
    out["avg@5"] = round(sum(acs) / 5, 4) if n else 0.0
    return out
