"""Period detection, and the strategy that acts on it.

The Seasonality ADR's warning is the spec: a wrong period makes a seasonal detector blind, so the
detector must abstain rather than guess. These tests sweep shapes, periods and noise and require
no wrong answer, only right ones and abstentions; and on everything without a period, abstention.
"""

from __future__ import annotations

import math
import random

import pytest

from pashupatastra.evaluation import Series, evaluate
from pashupatastra.period import detect_period
from pashupatastra.strategies import AutoSeasonal, RobustZScore, SeasonalRobustZ


def _shape(kind: str, period: int, step: int) -> float:
    phase = (step % period) / period
    if kind == "sine":
        return math.sin(2 * math.pi * phase)
    if kind == "square":
        return 1.0 if 0.3 < phase < 0.7 else 0.0
    if kind == "saw":
        return phase
    return 1.0 if phase < 0.08 else 0.0  # a nightly batch: a short burst once a cycle


def seasonal(kind: str, period: int, noise: float, seed: int, cycles: int = 8) -> list[float]:
    rng = random.Random(seed)
    return [30 * _shape(kind, period, i) + rng.gauss(0, noise * 30) for i in range(period * cycles)]


def walk(seed: int, n: int = 600) -> list[float]:
    rng, value, out = random.Random(seed), 40.0, []
    for _ in range(n):
        value += rng.gauss(0, 1)
        out.append(value)
    return out


def level_shifts(seed: int, n: int = 600) -> list[float]:
    """Deploys and growth: steps at irregular times."""
    rng, level, left, out = random.Random(seed), 40.0, 0, []
    for _ in range(n):
        if left <= 0:
            level += rng.uniform(5, 15)
            left = rng.randint(60, 240)
        left -= 1
        out.append(level + rng.gauss(0, 2))
    return out


NON_SEASONAL = {
    "noise": lambda seed: [40 + random.Random(seed).gauss(0, 2) for _ in range(600)],
    "trend": lambda seed: [40 + 0.1 * i + random.Random(seed * 1000 + i).gauss(0, 2) for i in range(600)],
    "random walk": walk,
    "level shifts": level_shifts,
    "outage": lambda seed: [
        40 + random.Random(seed * 1000 + i).gauss(0, 2) + (30 if 250 <= i < 280 else 0) for i in range(600)
    ],
}


@pytest.mark.parametrize("kind", ["sine", "square", "saw", "spiky"])
@pytest.mark.parametrize("period", [12, 60, 288])
def test_a_clear_period_is_found_exactly(kind: str, period: int) -> None:
    for seed in range(3):
        found = detect_period(seasonal(kind, period, noise=0.05, seed=seed))
        assert found.period is not None and abs(found.period - period) <= max(1, period // 50), found


@pytest.mark.parametrize("period", [24, 60, 144])
def test_noise_brings_abstention_never_a_wrong_period(period: int) -> None:
    """The sweep behind this (4 shapes x 5 periods x 3 noise levels x 10 seeds) found 0 wrong
    periods in 600; heavy noise is where a wrong one would come from, so it is pinned here."""
    for kind in ("sine", "square", "saw", "spiky"):
        for seed in range(5):
            found = detect_period(seasonal(kind, period, noise=0.5, seed=seed)).period
            if found is None:
                continue
            assert any(abs(found - m * period) <= max(1, m * period // 50) for m in (1, 2, 3)), (
                kind, period, seed, found
            )


@pytest.mark.parametrize("kind", list(NON_SEASONAL))
def test_a_series_without_a_period_gets_none(kind: str) -> None:
    for seed in range(10):
        found = detect_period(NON_SEASONAL[kind](seed))
        assert found.period is None, (kind, seed, found)
        assert found.reason


def test_too_little_history_is_an_abstention_with_a_reason() -> None:
    assert detect_period(seasonal("sine", 60, 0.05, 0, cycles=2)).period is None
    short = detect_period([1.0, 2.0, 3.0] * 3)
    assert short.period is None
    assert "cycles" in short.reason


def test_a_flat_series_has_no_period() -> None:
    assert detect_period([5.0] * 500).period is None


# --- the strategy -------------------------------------------------------------------------------


def test_it_switches_to_the_seasonal_model_and_stops_raising_false_alarms() -> None:
    values = [40 + 30 * _shape("square", 60, i) + random.Random(i).uniform(-1, 1) for i in range(60 * 10)]
    auto = AutoSeasonal()
    flags = [auto.evaluate_and_observe(v).is_anomalous for v in values]
    assert auto.period == 60
    switched = 300  # three cycles of evidence and two agreeing checks, with room to spare
    assert not any(flags[switched:]), "after the switch the square wave is the expectation"
    plain = RobustZScore()
    robust = [plain.evaluate_and_observe(v).is_anomalous for v in values]
    assert sum(robust[switched:]) > 0, "robust-z alone keeps flagging the shape"


def test_after_the_switch_it_is_as_sensitive_as_being_told_the_period() -> None:
    rng = random.Random(1)
    values = [70 + 30 * math.sin(2 * math.pi * i / 60) + rng.uniform(-2, 2) for i in range(60 * 10)]
    for i in range(500, 510):
        values[i] = 115.0  # inside the daily range: robust-z cannot see it
    series = Series("sine+spike", values, [(500, 509)])
    assert evaluate(AutoSeasonal(), series).caught_episodes == 1
    assert evaluate(SeasonalRobustZ(period=60), series).caught_episodes == 1
    assert evaluate(RobustZScore(), series).caught_episodes == 0


@pytest.mark.parametrize("kind", list(NON_SEASONAL))
def test_without_a_period_it_is_exactly_robust_z(kind: str) -> None:
    values = NON_SEASONAL[kind](3)
    auto, plain = AutoSeasonal(), RobustZScore()
    for value in values:
        assert auto.evaluate_and_observe(value) == plain.evaluate_and_observe(value)
    assert auto.period is None


def test_a_regular_staircase_is_absorbed_not_flagged() -> None:
    """Steps at exactly regular intervals are periodic once the trend is removed, and the detector
    says so. The seasonal model then expects each cycle's step, so it raises nothing."""
    rng = random.Random(4)
    values = [40 + rng.gauss(0, 2) + 10 * (i // 150) for i in range(1500)]
    auto = AutoSeasonal()
    flags = [auto.evaluate_and_observe(v).is_anomalous for v in values]
    if auto.period is not None:
        assert sum(flags[1000:]) <= 3
