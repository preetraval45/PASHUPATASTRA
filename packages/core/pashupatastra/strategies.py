"""Detection strategies, behind one interface.

The roadmap says ML detection ships "only if it beats the baseline on the
benchmark". That is a decision rule, and a rule with no way to measure it is a
preference. This module is the measuring apparatus: every detector — statistical
or learned — implements the same interface, so the comparison is a run rather
than an argument.

Three strategies ship, all statistical, because the first thing worth knowing is
whether the *simplest* one is already good enough. A candidate has to beat the
best of these, not the worst.

An ML strategy would implement the same protocol. It would also have to satisfy
the constraint that outranks accuracy: a finding must cite the evidence behind
it (Grounding ADR). A model that scores well but cannot say which observations
drove the score produces findings the reasoning layer must suppress, so its
accuracy never reaches an operator.
"""

from __future__ import annotations

import statistics
from collections import deque
from typing import Protocol

from .baselines import MIN_SAMPLES, Band, Baseline, Reading


class DetectionStrategy(Protocol):
    """What every detector must provide.

    Deliberately narrow: judge one value, then learn it. A strategy needing to
    see the future, or the whole series at once, cannot run online against a
    live stream and so cannot be deployed however well it benchmarks.
    """

    name: str

    def evaluate_and_observe(self, value: float) -> Reading: ...

    def __len__(self) -> int: ...


class RobustZScore:
    """Median and MAD. The incumbent — see `baselines.py`."""

    name = "robust-z"

    def __init__(self, window: int = 200, threshold: float = 3.0) -> None:
        self._baseline = Baseline(key=self.name, window=window, threshold=threshold)

    def evaluate_and_observe(self, value: float) -> Reading:
        return self._baseline.evaluate_and_observe(value)

    def __len__(self) -> int:
        return len(self._baseline)


class Ewma:
    """Exponentially weighted moving average and deviation.

    Adapts faster to genuine level shifts than a rolling median — a service that
    legitimately doubles its traffic stops being flagged sooner. The cost is the
    incumbent's whole advantage: the anomaly *is* absorbed, so a sustained
    outage gradually becomes the new normal. Included precisely so that
    trade-off is measured rather than asserted.
    """

    name = "ewma"

    def __init__(self, alpha: float = 0.05, threshold: float = 3.0) -> None:
        self.alpha = alpha
        self.threshold = threshold
        self._mean: float | None = None
        self._variance = 0.0
        self._n = 0

    def evaluate_and_observe(self, value: float) -> Reading:
        reading = self.evaluate(value)
        self.observe(value)
        return reading

    def evaluate(self, value: float) -> Reading:
        if self._n < MIN_SAMPLES or self._mean is None:
            return Reading(Band.UNKNOWN, value, self._mean, 0.0, self._n)

        spread = self._variance**0.5
        if spread == 0:
            band = Band.NORMAL if value == self._mean else (
                Band.HIGH if value > self._mean else Band.LOW
            )
            deviation = 0.0 if band is Band.NORMAL else self.threshold
            return Reading(band, value, self._mean, deviation, self._n)

        deviation = (value - self._mean) / spread
        if abs(deviation) < self.threshold:
            band = Band.NORMAL
        else:
            band = Band.HIGH if deviation > 0 else Band.LOW
        return Reading(band, value, self._mean, round(deviation, 3), self._n)

    def observe(self, value: float) -> None:
        self._n += 1
        if self._mean is None:
            self._mean = value
            return
        delta = value - self._mean
        self._mean += self.alpha * delta
        self._variance = (1 - self.alpha) * (self._variance + self.alpha * delta * delta)

    def __len__(self) -> int:
        return self._n


class SeasonalNaive:
    """Compares a value with the same point in the previous cycle.

    The one thing neither other strategy handles: a metric with a daily shape.
    Morning traffic ramping is not an anomaly, but to a flat baseline it looks
    like one every single day — and a detector that cries wolf each morning is
    one operators learn to ignore, which is worse than no detector.

    Needs a full cycle of history before it can say anything, which is honest
    but expensive, so it is a candidate rather than the default.
    """

    name = "seasonal-naive"

    def __init__(self, period: int = 288, threshold: float = 3.0) -> None:
        self.period = period
        self.threshold = threshold
        self._history: deque[float] = deque(maxlen=period * 3)
        self._residuals: deque[float] = deque(maxlen=period)

    def evaluate_and_observe(self, value: float) -> Reading:
        reading = self.evaluate(value)
        self.observe(value)
        return reading

    def evaluate(self, value: float) -> Reading:
        if len(self._history) < self.period or len(self._residuals) < MIN_SAMPLES:
            return Reading(Band.UNKNOWN, value, None, 0.0, len(self._history))

        expected = self._history[-self.period]
        spread = statistics.median([abs(r) for r in self._residuals]) / 0.6745
        if spread == 0:
            band = Band.NORMAL if value == expected else (
                Band.HIGH if value > expected else Band.LOW
            )
            deviation = 0.0 if band is Band.NORMAL else self.threshold
            return Reading(band, value, expected, deviation, len(self._history))

        deviation = (value - expected) / spread
        if abs(deviation) < self.threshold:
            band = Band.NORMAL
        else:
            band = Band.HIGH if deviation > 0 else Band.LOW
        return Reading(band, value, expected, round(deviation, 3), len(self._history))

    def observe(self, value: float) -> None:
        if len(self._history) >= self.period:
            self._residuals.append(value - self._history[-self.period])
        self._history.append(value)

    def __len__(self) -> int:
        return len(self._history)


STRATEGIES: dict[str, type] = {
    RobustZScore.name: RobustZScore,
    Ewma.name: Ewma,
    SeasonalNaive.name: SeasonalNaive,
}
