"""Period detection by autocorrelation — the opt-in for seasonal detection, made automatic.

The Seasonality ADR kept robust-z as the default because a seasonal detector told the wrong period
is not noisy but *blind*: a spike at 130 went unseen at every wrong period it tried. So this module
is built to abstain. It returns a period only when the evidence for it is unmistakable, and `None`
otherwise, and a `None` leaves the metric on robust-z with its blindness still reported as
`unmodelled`. A missed period costs what it costs today; a wrong one would cost silence.

The evidence it asks for, in order:

1. Enough history: at least `min_cycles` whole cycles of the candidate.
2. A peak, not a slope. A trend or a random walk has an autocorrelation that falls away
   smoothly; a period has one that falls *and comes back*. A candidate must rise at least
   `min_prominence` above the lowest autocorrelation at any shorter lag.
3. Strength: the autocorrelation at the candidate is at least `min_strength`.
4. Recurrence: it is strong again at twice the lag. A one-off coincidence of shape does not
   repeat; a cycle does.

Of the candidates that pass, the shortest one nearly as strong as the best is chosen, since a
period's multiples are peaks too.

Pure Python, no numpy, like the rest of core: the series it reads are minutes to days of one
metric, and the work is one pass per lag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PeriodEstimate:
    period: int | None
    strength: float
    reason: str

    @property
    def found(self) -> bool:
        return self.period is not None


def _detrended(values: Sequence[float]) -> list[float]:
    """Remove the least-squares line, so a trend is not read as one very long cycle."""
    n = len(values)
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    sxx = sum((i - mean_x) ** 2 for i in range(n))
    slope = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values)) / sxx if sxx else 0.0
    return [v - mean_y - slope * (i - mean_x) for i, v in enumerate(values)]


def autocorrelation(values: Sequence[float], max_lag: int) -> list[float]:
    """Autocorrelation at lags 0..max_lag, each normalised by its own number of pairs."""
    x = _detrended(values)
    n = len(x)
    variance = sum(v * v for v in x) / n
    if variance == 0:
        return [1.0] + [0.0] * max_lag
    return [1.0] + [
        sum(x[i] * x[i + lag] for i in range(n - lag)) / (n - lag) / variance
        for lag in range(1, max_lag + 1)
    ]


def detect_period(
    values: Sequence[float],
    min_period: int = 4,
    max_period: int | None = None,
    min_cycles: int = 3,
    min_strength: float = 0.5,
    min_prominence: float = 0.3,
) -> PeriodEstimate:
    """The series' period, or `None` with the reason it would not commit to one."""
    n = len(values)
    longest = n // max(min_cycles, 2)
    if max_period is not None:
        longest = min(longest, max_period)
    if longest < min_period:
        return PeriodEstimate(None, 0.0, f"{n} samples hold fewer than {min_cycles} cycles of any period")

    # Recurrence is checked at twice the lag, so the curve is needed that far.
    acf = autocorrelation(values, min(2 * longest + 1, n - 2))

    # Hills, not local maxima: noise puts small bumps on the rising edge of a real peak, and the
    # first bump is not the period. Each stretch where the curve stays above `min_strength` is one
    # candidate, taken at its highest point.
    candidates: list[tuple[int, float]] = []
    lowest = acf[1]
    lag = 2
    while lag <= longest:
        lowest = min(lowest, acf[lag - 1])
        if acf[lag] < min_strength:
            lag += 1
            continue
        start = lag
        while lag + 1 < len(acf) and acf[lag + 1] >= min_strength:
            lag += 1
        # The top of a noisy hill is located on the curve averaged over a few lags either side;
        # the single highest lag wanders by a few percent of the period.
        half = max(1, start // 25)

        def smoothed(k: int) -> float:
            window = acf[max(1, k - half) : k + half + 1]
            return sum(window) / len(window)

        top = max(range(start, lag + 1), key=smoothed)
        lag += 1
        strength = acf[top]
        if top < min_period or top > longest or strength - lowest < min_prominence:
            continue
        reach = max(1, top // 20)
        twice = acf[2 * top - reach : 2 * top + reach + 1]
        if len(twice) < 2 * reach + 1 or max(twice) < min_strength:
            continue
        candidates.append((top, strength))

    if not candidates:
        return PeriodEstimate(None, round(max(acf[min_period : longest + 1], default=0.0), 3),
                              "no autocorrelation peak that is strong, prominent and recurs")

    best = max(strength for _, strength in candidates)
    lag, strength = next((lag, s) for lag, s in candidates if s >= 0.9 * best)
    return PeriodEstimate(lag, round(strength, 3), f"peak at lag {lag}, recurring at {2 * lag}")
