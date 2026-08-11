"""Detector evaluation.

The harness decides whether a future ML detector may ship, so its own scoring
has to be right first. These tests are mostly about the ways a scoring function
can flatter a bad detector.
"""

from __future__ import annotations

import random

from pashupatastra.evaluation import Score, Series, compare, evaluate, winner
from pashupatastra.strategies import STRATEGIES, Ewma, RobustZScore, SeasonalNaive


def flat(n: int = 300, value: float = 40.0, jitter: float = 2.0, seed: int = 3) -> list[float]:
    random.seed(seed)
    return [value + random.uniform(-jitter, jitter) for _ in range(n)]


def with_outage(n: int = 300, start: int = 200, length: int = 30) -> Series:
    values = flat(n)
    for i in range(start, start + length):
        values[i] = 95.0
    return Series(name="outage", values=values, anomalies=[(start, start + length)])


def seasonal(cycles: int = 4, period: int = 60, spike_at: int | None = None) -> Series:
    """A daily shape: a flat baseline sees the morning ramp as an anomaly every
    single cycle, and a detector that cries wolf each morning gets ignored."""
    random.seed(7)
    values: list[float] = []
    for _ in range(cycles):
        for step in range(period):
            base = 40 + 30 * (1 if period * 0.3 < step < period * 0.7 else 0)
            values.append(base + random.uniform(-1, 1))

    anomalies = []
    if spike_at is not None:
        for i in range(spike_at, spike_at + 10):
            values[i] = 200.0
        anomalies = [(spike_at, spike_at + 10)]
    return Series(name="seasonal", values=values, anomalies=anomalies)


# --- the harness itself ------------------------------------------------------


def test_clean_series_produces_no_true_positives() -> None:
    score = evaluate(RobustZScore(), Series(name="clean", values=flat()))
    assert score.true_positives == 0
    assert score.total_episodes == 0


def test_warmup_is_neither_credited_nor_penalised() -> None:
    """Scoring silence as a miss would reward strategies that guess early."""
    series = Series(name="short", values=flat(n=10))
    score = evaluate(RobustZScore(), series)
    assert score.warmup_samples == 10
    assert score.true_positives == score.false_positives == 0


def test_recall_counts_episodes_not_samples() -> None:
    """A 30-minute outage is one thing that happened. Counting its 360 samples
    separately would let a detector look excellent by firing continuously
    through one long incident while missing every short one."""
    score = evaluate(RobustZScore(), with_outage(length=40))
    assert score.total_episodes == 1
    assert score.caught_episodes == 1
    assert score.recall == 1.0
    assert score.true_positives > 1, "many samples flagged, but one episode caught"


def test_lead_time_rewards_firing_early() -> None:
    """Perfect precision and recall at minute nine of a ten-minute outage tells
    an operator nothing they did not already know."""
    early = Score(strategy="a", series="s", lead_samples=[28])
    late = Score(strategy="b", series="s", lead_samples=[2])
    assert early.mean_lead > late.mean_lead


def test_missed_episode_is_recorded() -> None:
    series = Series(name="never-flagged", values=flat(), anomalies=[(100, 110)])
    score = evaluate(RobustZScore(), series)
    assert score.missed_episodes == 1
    assert score.recall == 0.0


def test_precision_falls_with_false_positives() -> None:
    score = Score(strategy="s", series="x", true_positives=10, false_positives=90)
    assert score.precision == 0.1


def test_f1_is_zero_when_either_half_is() -> None:
    assert Score(strategy="s", series="x").f1 == 0.0


def test_false_alarm_rate_is_reported_per_thousand() -> None:
    """The number an operator actually feels."""
    score = Score(
        strategy="s", series="x", true_positives=5, false_positives=5, warmup_samples=990
    )
    assert score.false_alarms_per_1000 == 5.0


# --- the strategies ----------------------------------------------------------


def test_every_registered_strategy_runs_online() -> None:
    """A strategy that needs the whole series at once cannot run against a live
    stream, so it could never be deployed however well it benchmarks."""
    series = with_outage()
    for factory in STRATEGIES.values():
        score = evaluate(factory(), series)
        assert isinstance(score.precision, float)


def test_robust_z_catches_a_sustained_outage() -> None:
    score = evaluate(RobustZScore(), with_outage())
    assert score.recall == 1.0
    assert score.precision > 0.9


def test_ewma_absorbs_a_sustained_outage() -> None:
    """The documented trade-off, measured rather than asserted: EWMA adapts to
    genuine level shifts faster, and pays for it by treating a long outage as
    the new normal."""
    outage = with_outage(length=60)
    robust = evaluate(RobustZScore(), outage)
    ewma = evaluate(Ewma(), outage)
    assert robust.true_positives > ewma.true_positives


def test_seasonal_naive_beats_a_flat_baseline_on_seasonal_data() -> None:
    """The case that motivates it: a flat baseline flags the morning ramp every
    cycle, and a detector that cries wolf daily is one operators ignore."""
    series = seasonal(cycles=6, period=60)
    flat_score = evaluate(RobustZScore(), series)
    seasonal_score = evaluate(SeasonalNaive(period=60), series)
    assert seasonal_score.false_positives < flat_score.false_positives


def test_comparison_produces_one_row_per_strategy_and_series() -> None:
    rows = compare(list(STRATEGIES.values()), [with_outage(), Series("clean", flat())])
    assert len(rows) == len(STRATEGIES) * 2


def test_winner_averages_across_series_rather_than_pooling() -> None:
    """Otherwise a strategy wins by being excellent on the one longest series
    and useless on every other."""
    rows = [
        {"strategy": "specialist", "series": "a", "f1": 1.0},
        {"strategy": "specialist", "series": "b", "f1": 0.0},
        {"strategy": "generalist", "series": "a", "f1": 0.7},
        {"strategy": "generalist", "series": "b", "f1": 0.7},
    ]
    assert winner(rows) == "generalist"


def test_winner_of_an_empty_comparison_is_none() -> None:
    assert winner([]) is None
