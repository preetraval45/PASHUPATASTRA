"""Which differences between two arms survive chance (RP-10).

Two tests, both on *paired* data — the same scenarios, the same run index — because
the arms faced identical incidents and ignoring that throws away the pairing
that makes small benchmarks usable (Dror et al., ACL 2018):

* **McNemar's exact test** on per-run correctness. Only the discordant pairs
  carry information — runs one arm got right and the other wrong — and with
  few of them the exact binomial form is the honest one.
* **A paired bootstrap** confidence interval on the difference in false-
  remediation rate, resampling **scenarios** rather than runs. Three runs of
  one scenario are not three independent pieces of evidence, and resampling
  them as if they were would make every interval too narrow.

Pure arithmetic: no NumPy, no model, no cloud — it runs anywhere core does.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class McNemar:
    only_a: int
    """Runs arm A got right and arm B got wrong."""
    only_b: int
    p_value: float

    @property
    def discordant(self) -> int:
        return self.only_a + self.only_b


def mcnemar(pairs: Sequence[tuple[bool, bool]]) -> McNemar:
    """Exact two-sided McNemar test on (a_correct, b_correct) pairs."""
    only_a = sum(1 for a, b in pairs if a and not b)
    only_b = sum(1 for a, b in pairs if b and not a)
    n = only_a + only_b
    if n == 0:
        return McNemar(only_a, only_b, 1.0)
    k = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return McNemar(only_a, only_b, min(1.0, 2 * tail))


def bootstrap_difference(
    a: dict[str, list],
    b: dict[str, list],
    statistic: Callable[[list], float | None],
    reps: int = 2000,
    seed: int = 7,
    level: float = 0.95,
) -> tuple[float, float] | None:
    """CI for statistic(A) − statistic(B), resampling shared scenarios.

    `a` and `b` map scenario id → that arm's records for it. A resample draws
    scenario ids with replacement and takes *all* runs of each drawn scenario
    from both arms, so the pairing and the within-scenario correlation both
    survive. Returns None when the statistic is undefined (no actions taken).
    """
    shared = sorted(set(a) & set(b))
    if not shared:
        return None
    rng = random.Random(seed)
    diffs = []
    for _ in range(reps):
        draw = [rng.choice(shared) for _ in shared]
        sa = statistic([r for s in draw for r in a[s]])
        sb = statistic([r for s in draw for r in b[s]])
        if sa is not None and sb is not None:
            diffs.append(sa - sb)
    if len(diffs) < reps // 2:
        return None
    diffs.sort()
    lo = diffs[int((1 - level) / 2 * len(diffs))]
    hi = diffs[min(len(diffs) - 1, int((1 + level) / 2 * len(diffs)))]
    return (round(lo, 4), round(hi, 4))
