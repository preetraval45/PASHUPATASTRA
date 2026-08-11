"""Baselines.

The tests that matter are about what the baseline refuses to claim: that it
knows something from four samples, and that an ongoing incident is normal.
"""

from __future__ import annotations

import random

import pytest

from pashupatastra.baselines import (
    MIN_SAMPLES,
    Baseline,
    BaselineStore,
    Band,
)


def warmed(values: list[float], **kwargs) -> Baseline:
    baseline = Baseline(key="test", **kwargs)
    for value in values:
        baseline.observe(value)
    return baseline


def steady(n: int = 50, value: float = 40.0, jitter: float = 2.0) -> list[float]:
    random.seed(11)
    return [value + random.uniform(-jitter, jitter) for _ in range(n)]


def test_cold_baseline_reports_unknown_not_normal() -> None:
    """'I don't know' and 'that's fine' are different claims, and only one of
    them gets an incident closed early."""
    baseline = warmed([40.0] * (MIN_SAMPLES - 1))
    reading = baseline.evaluate(40.0)
    assert reading.band is Band.UNKNOWN
    assert not reading.is_anomalous
    assert reading.confidence == 0.0


def test_warm_baseline_accepts_a_normal_value() -> None:
    reading = warmed(steady()).evaluate(41.0)
    assert reading.band is Band.NORMAL


def test_spike_is_flagged_high() -> None:
    reading = warmed(steady()).evaluate(95.0)
    assert reading.band is Band.HIGH
    assert reading.deviation > 3


def test_drop_is_flagged_low() -> None:
    """Traffic falling off a cliff is as much an incident as latency rising."""
    reading = warmed(steady()).evaluate(2.0)
    assert reading.band is Band.LOW
    assert reading.deviation < -3


def test_an_ongoing_incident_does_not_become_the_baseline() -> None:
    """The failure mode of mean-and-stddev: a sustained outage inflates both, so
    the second occurrence scores lower than the first and eventually reads as
    normal. Median and MAD resist a minority of extreme samples."""
    baseline = warmed(steady(n=60))

    # Ten minutes of sustained failure, learned as it happens.
    for _ in range(10):
        baseline.evaluate_and_observe(95.0)

    still_bad = baseline.evaluate(95.0)
    assert still_bad.band is Band.HIGH, "a sustained outage must not normalize itself"


def test_evaluation_precedes_learning() -> None:
    """A single extreme value must not partially normalize itself in the act of
    being measured."""
    baseline = warmed(steady())
    before = baseline.median
    reading = baseline.evaluate_and_observe(95.0)

    assert reading.band is Band.HIGH
    assert reading.median == before, "judged against history, not against itself"


def test_flat_metric_flags_any_change_without_infinite_deviation() -> None:
    baseline = warmed([1.0] * 40)
    assert baseline.evaluate(1.0).band is Band.NORMAL

    changed = baseline.evaluate(0.0)
    assert changed.band is Band.LOW
    assert changed.deviation == baseline.threshold, "flagged, but not dominating a ranking"


def test_window_is_bounded() -> None:
    baseline = warmed([1.0] * 500, window=100)
    assert len(baseline) == 100


def test_confidence_rises_with_evidence() -> None:
    """A 4-sigma reading from 25 samples is a weaker claim than the same
    deviation from 200 — and confidence feeds effective risk, so overstating it
    would quietly widen what the system may do."""
    thin = warmed(steady(n=MIN_SAMPLES)).evaluate(95.0)
    thick = warmed(steady(n=200)).evaluate(95.0)
    assert thick.confidence > thin.confidence


def test_confidence_is_bounded() -> None:
    reading = warmed(steady(n=300)).evaluate(10_000.0)
    assert 0.0 <= reading.confidence <= 1.0


def test_store_keeps_baselines_per_entity_and_metric() -> None:
    """90% CPU is unremarkable on a batch worker and alarming on an API pod. A
    shared baseline would learn the average of two unrelated populations."""
    store = BaselineStore()
    for value in steady(n=40, value=90.0):
        store.evaluate_and_observe("service:worker", "cpu", value)
    for value in steady(n=40, value=20.0):
        store.evaluate_and_observe("service:api", "cpu", value)

    assert store.evaluate_and_observe("service:worker", "cpu", 90.0).band is Band.NORMAL
    assert store.evaluate_and_observe("service:api", "cpu", 90.0).band is Band.HIGH


def test_store_reports_how_much_of_it_is_warm() -> None:
    """An unwarmed detector's silence must not be read as an all-clear."""
    store = BaselineStore()
    for value in steady(n=40):
        store.evaluate_and_observe("service:api", "cpu", value)
    store.evaluate_and_observe("service:new", "cpu", 1.0)

    assert len(store) == 2
    assert store.warm == 1


@pytest.mark.parametrize("outliers", [1, 3, 5])
def test_a_few_outliers_do_not_move_the_median_much(outliers: int) -> None:
    clean = warmed(steady(n=60))
    polluted = warmed(steady(n=60) + [900.0] * outliers)
    assert abs((polluted.median or 0) - (clean.median or 0)) < 5
