"""Detection strategy benchmark.

Produces the measurement the roadmap's seasonality gap needs: how each strategy
behaves on series shaped like the ones it will actually meet, rather than only
on the flat series that flatter a flat baseline.

The gap this exists to settle: robust-z is the shipped default and scores
hundreds of false alarms per 1000 on a daily-shaped series where EWMA scores
tens. Almost every metric worth watching is daily-shaped, because human activity
is, so the default is wrong for the common case. A detector that fires every
weekday morning trains operators to ignore it, and an ignored detector is worse
than an absent one — it produces the appearance of coverage.

Usage:  python scripts/benchdetect.py [--strict]

`--strict` exits non-zero if the chosen default is beaten on any workload by
more than the stated tolerance, so CI can hold the decision in place.

Deterministic: fixed seeds throughout, so reruns are comparable and a change in
the numbers means a change in the code.
"""

from __future__ import annotations

import argparse
import math
import random
import sys

sys.path.insert(0, "packages/core")

from pashupatastra.baselines import Band  # noqa: E402
from pashupatastra.evaluation import Series, evaluate  # noqa: E402
from pashupatastra.strategies import (  # noqa: E402
    Ewma,
    RobustZScore,
    SeasonalNaive,
    SeasonalRobustZ,
)

PERIOD = 60
"""Samples per cycle. 60 stands in for a day at one sample per minute-ish; the
shape is what matters, not the wall-clock mapping."""

TOLERANCE = 1.5
"""How much worse than the best strategy the default may be on any workload,
as a multiple of false alarms per 1000. Chosen so a default has to be broadly
reasonable rather than optimal everywhere — a strategy that wins one workload
outright and loses another badly is not a good default."""


# --- workloads ---------------------------------------------------------------
#
# Each is a shape a real metric takes. The seasonal ones are the point, but the
# flat ones have to stay in: a fix for seasonality that breaks the flat case has
# traded one blind spot for another.


def _noise(seed: int) -> random.Random:
    return random.Random(seed)


def flat(n: int = 400, value: float = 40.0, jitter: float = 2.0, seed: int = 3) -> Series:
    rng = _noise(seed)
    return Series("flat", [value + rng.uniform(-jitter, jitter) for _ in range(n)])


def flat_with_outage(n: int = 400, start: int = 250, length: int = 30) -> Series:
    rng = _noise(3)
    values = [40.0 + rng.uniform(-2, 2) for _ in range(n)]
    for i in range(start, start + length):
        values[i] = 95.0
    return Series("flat+outage", values, [(start, start + length)])


def square_seasonal(cycles: int = 8) -> Series:
    """The harsh case: an instantaneous step up and down each cycle.

    Kept because it is what the existing test suite uses, so the numbers here
    are comparable with the figure already in the roadmap. It overstates the
    problem — real traffic ramps rather than steps — which is why the sinusoidal
    workload below exists beside it.
    """
    rng = _noise(7)
    values = [
        40 + (30 if PERIOD * 0.3 < step < PERIOD * 0.7 else 0) + rng.uniform(-1, 1)
        for _ in range(cycles)
        for step in range(PERIOD)
    ]
    return Series("seasonal-square", values)


def sine_seasonal(cycles: int = 8) -> Series:
    """The realistic case: a smooth daily ramp, peak to trough."""
    rng = _noise(11)
    values = [
        70 + 30 * math.sin(2 * math.pi * step / PERIOD) + rng.uniform(-2, 2)
        for _ in range(cycles)
        for step in range(PERIOD)
    ]
    return Series("seasonal-sine", values)


def sine_seasonal_with_spike(cycles: int = 8, spike_at: int = 400, length: int = 10) -> Series:
    """Seasonal, with a genuine incident inside it.

    The workload that separates a detector from a smoother: suppressing the
    daily shape is only useful if a real spike still gets through.
    """
    series = sine_seasonal(cycles)
    values = list(series.values)
    for i in range(spike_at, spike_at + length):
        values[i] = 260.0
    return Series("seasonal+spike", values, [(spike_at, spike_at + length)])


def sine_seasonal_with_spike_at(
    magnitude: float, cycles: int = 8, spike_at: int = 400, length: int = 10
) -> Series:
    """Seasonal, with an incident of a chosen size.

    Sweeping the magnitude is what exposes blindness. A strategy whose band has
    been widened by seasonal spread still scores a clean zero on false alarms —
    it simply stops seeing anything, which no false-alarm metric can reveal.
    """
    values = list(sine_seasonal(cycles).values)
    for i in range(spike_at, spike_at + length):
        values[i] = magnitude
    return Series(f"sine+spike@{magnitude:g}", values, [(spike_at, spike_at + length)])


def seasonal_with_trend(cycles: int = 8) -> Series:
    """Daily shape plus steady growth — a service gaining traffic week on week.

    Separates the two failure modes the roadmap conflates: a strategy can handle
    seasonality and still drift on trend, and the fixes differ.
    """
    rng = _noise(13)
    values = [
        70 + 30 * math.sin(2 * math.pi * step / PERIOD) + 0.05 * (cycle * PERIOD + step)
        + rng.uniform(-2, 2)
        for cycle in range(cycles)
        for step in range(PERIOD)
    ]
    return Series("seasonal+trend", values)


WORKLOADS = [
    flat,
    flat_with_outage,
    square_seasonal,
    sine_seasonal,
    sine_seasonal_with_spike,
    seasonal_with_trend,
]

CANDIDATES = {
    "robust-z": lambda: RobustZScore(),
    "ewma": lambda: Ewma(),
    "seasonal-naive": lambda: SeasonalNaive(period=PERIOD),
    "seasonal-robust-z": lambda: SeasonalRobustZ(period=PERIOD),
}


# --- where a strategy fires --------------------------------------------------


def phase_breakdown(strategy, series: Series) -> dict[str, int]:
    """Which part of the cycle the false alarms land in.

    The roadmap asks whether robust-z fires on the peak, the trough, or the
    transition, because the answer changes the fix. Firing on peak and trough
    means the baseline is centred and the shape is simply too wide for it.
    Firing on transitions means it is tracking the level but lagging the rate of
    change, which a different strategy solves.
    """
    counts = {"rising": 0, "peak": 0, "falling": 0, "trough": 0}
    for index, value in enumerate(series.values):
        reading = strategy.evaluate_and_observe(value)
        if reading.band is Band.UNKNOWN or not reading.is_anomalous:
            continue
        if series.is_anomalous(index):
            continue
        position = (index % PERIOD) / PERIOD
        if position < 0.25:
            counts["rising"] += 1
        elif position < 0.5:
            counts["peak"] += 1
        elif position < 0.75:
            counts["falling"] += 1
        else:
            counts["trough"] += 1
    return counts


# --- reporting ---------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if the recommended strategy is beaten by more than the tolerance",
    )
    parser.add_argument(
        "--recommended",
        default="seasonal-robust-z",
        help="the strategy recorded as best for seasonal metrics (ADR Seasonality)",
    )
    args = parser.parse_args()
    recommended = args.recommended

    series_list = [make() for make in WORKLOADS]

    print(f"{'workload':<22}{'strategy':<20}{'FA/1000':>9}{'prec':>7}{'recall':>8}{'lead':>7}")
    print("-" * 73)

    worst: dict[str, float] = {}
    for series in series_list:
        for name, factory in CANDIDATES.items():
            score = evaluate(factory(), series)
            fa = score.false_alarms_per_1000
            worst[name] = max(worst.get(name, 0.0), fa)
            recall = f"{score.recall:.2f}" if series.anomalies else "  —"
            lead = f"{score.mean_lead:.0f}" if series.anomalies else "  —"
            print(
                f"{series.name:<22}{name:<20}{fa:>9.1f}"
                f"{score.precision:>7.2f}{recall:>8}{lead:>7}"
            )
        print()

    print("worst-case false alarms per 1000, across all workloads:")
    ranked = sorted(worst.items(), key=lambda kv: kv[1])
    for name, value in ranked:
        marker = "  <- recommended for seasonal metrics" if name == recommended else ""
        print(f"  {name:<20}{value:>9.1f}{marker}")

    print("\nwhere robust-z's false alarms land on the square workload:")
    for phase, count in phase_breakdown(RobustZScore(), square_seasonal()).items():
        print(f"  {phase:<10}{count:>6}")

    print(
        "\nSENSITIVITY — the measurement that actually decides this.\n"
        "A seasonal series peaking near 100. How large must a genuine spike be\n"
        "before each strategy notices it? Lower is better; a detector that only\n"
        "wakes for catastrophes is silent for everything an operator could still fix."
    )
    print(f"\n{'spike':<10}" + "".join(f"{n:>20}" for n in CANDIDATES))
    print("-" * (10 + 20 * len(CANDIDATES)))
    thresholds: dict[str, int | None] = {name: None for name in CANDIDATES}
    for magnitude in (110, 120, 130, 145, 160, 180, 200, 230, 260):
        cells = []
        for name, factory in CANDIDATES.items():
            score = evaluate(factory(), sine_seasonal_with_spike_at(magnitude))
            caught = score.caught_episodes == score.total_episodes
            if caught and thresholds[name] is None:
                thresholds[name] = magnitude
            cells.append(f"{'caught' if caught else 'missed':>20}")
        print(f"{magnitude:<10}" + "".join(cells))

    print("\nsmallest spike detected (series peaks at ~100):")
    for name, magnitude in sorted(
        thresholds.items(), key=lambda kv: (kv[1] is None, kv[1] or 0)
    ):
        shown = str(magnitude) if magnitude else "never"
        print(f"  {name:<20}{shown:>8}")

    print(
        "\nNOTE: robust-z remains the shipped default for unconfigured metrics.\n"
        "seasonal-robust-z wins here because it is told the period. Given the\n"
        "wrong period it loses sensitivity silently, and its warm-up is three\n"
        "cycles, so it is opt-in per metric rather than global. See ADR Seasonality."
    )

    best_name, best_value = ranked[0]
    recommended_value = worst[recommended]
    print()
    if best_name == recommended:
        print(
            f"'{recommended}' still has the best worst case ({recommended_value:.1f})."
        )
        return 0

    ratio = recommended_value / best_value if best_value else float("inf")
    verdict = "within" if ratio <= TOLERANCE else "OUTSIDE"
    print(
        f"'{recommended}' worst case {recommended_value:.1f} vs best "
        f"'{best_name}' {best_value:.1f} — {ratio:.2f}x, {verdict} tolerance {TOLERANCE}x."
    )
    if ratio > TOLERANCE and args.strict:
        print(
            "::error::the recorded recommendation is beaten by more than the tolerance",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
