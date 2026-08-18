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

from .baselines import (
    _MAD_TO_SIGMA,
    DEFAULT_WINDOW,
    MIN_SAMPLES,
    Band,
    Baseline,
    Reading,
)


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


class SeasonalRobustZ:
    """Robust statistics applied to the *residual* after the daily shape is
    removed. The default.

    Measurement drove this, and it corrected the assumption behind it. The
    roadmap recorded robust-z scoring ~859 false alarms per 1000 on a
    daily-shaped series and read that as "robust-z cannot handle seasonality".
    Re-running it across several shapes (`scripts/benchdetect.py`) says something
    narrower and more useful:

      * On a **square** wave — an instantaneous step up and down — robust-z does
        score ~900/1000. But real traffic ramps; it does not teleport.
      * On a **sine** wave, the realistic shape, robust-z scores **zero** false
        alarms. Not because it handles seasonality, but because the seasonal
        spread inflates its MAD until the band is wider than the data. On a
        series spanning 38–102 it will accept anything from -26 to 157.

    So the real cost of seasonality was never noise. It is **blindness**, and
    blindness is the more dangerous failure: a false alarm is visible and
    irritating, while a band three times too wide reports NORMAL and looks
    exactly like an all-clear. Measured, robust-z needs a spike near 200 before
    it reacts on a series that peaks at 100 — every smaller genuine incident
    passes as normal.

    The fix follows from that. Estimate what this point in the cycle usually
    looks like, subtract it, and judge what is left. The band then reflects the
    residual noise the metric actually has rather than the daily range it is
    supposed to have.

    **Per-phase median, not the previous cycle.** `SeasonalNaive` compares
    against the same point one cycle back, which has a defect the benchmark
    makes obvious: an incident becomes the *expectation* one period later, so
    every incident is followed by a guaranteed phantom exactly one cycle after
    it — its precision is pinned at 0.50 for this reason alone. A median across
    several cycles has no such echo, because one contaminated cycle cannot move
    a median of five.

    The cost is warm-up, and it is real: three full cycles before it will say
    anything. That is expensive and it is honest — `UNKNOWN` until it genuinely
    knows, per the rule in `baselines.py`.
    """

    name = "seasonal-robust-z"

    MIN_CYCLES = 3
    """Cycles of history per phase before judging. Three is the smallest number
    whose median survives one contaminated cycle."""

    def __init__(
        self,
        period: int = 288,
        cycles: int = 5,
        threshold: float = 3.0,
        window: int = DEFAULT_WINDOW,
    ) -> None:
        self.period = period
        self.cycles = cycles
        self.threshold = threshold
        self._phases: list[deque[float]] = [deque(maxlen=cycles) for _ in range(period)]
        self._residuals: deque[float] = deque(maxlen=window)
        self._n = 0

    def evaluate_and_observe(self, value: float) -> Reading:
        reading = self.evaluate(value)
        self.observe(value)
        return reading

    def _expected(self) -> float | None:
        history = self._phases[self._n % self.period]
        if len(history) < self.MIN_CYCLES:
            return None
        return statistics.median(history)

    def evaluate(self, value: float) -> Reading:
        expected = self._expected()
        if expected is None or len(self._residuals) < MIN_SAMPLES:
            return Reading(Band.UNKNOWN, value, expected, 0.0, self._n)

        residual = value - expected
        centre = statistics.median(self._residuals)
        spread = (
            statistics.median([abs(r - centre) for r in self._residuals]) / _MAD_TO_SIGMA
        )

        if spread == 0:
            if residual == centre:
                return Reading(Band.NORMAL, value, expected, 0.0, self._n)
            band = Band.HIGH if residual > centre else Band.LOW
            return Reading(band, value, expected, self.threshold, self._n)

        deviation = (residual - centre) / spread
        if abs(deviation) < self.threshold:
            band = Band.NORMAL
        else:
            band = Band.HIGH if deviation > 0 else Band.LOW
        return Reading(band, value, expected, round(deviation, 3), self._n)

    def observe(self, value: float) -> None:
        expected = self._expected()
        if expected is not None:
            # Residuals are recorded even when the value was anomalous. The
            # spread is a median absolute deviation, so a minority of extreme
            # residuals cannot inflate it — the same argument that makes the
            # non-seasonal baseline robust, and filtering them explicitly would
            # mean the detector deciding what counts as evidence about itself.
            self._residuals.append(value - expected)
        self._phases[self._n % self.period].append(value)
        self._n += 1

    def __len__(self) -> int:
        return self._n


STRATEGIES: dict[str, type] = {
    RobustZScore.name: RobustZScore,
    Ewma.name: Ewma,
    SeasonalNaive.name: SeasonalNaive,
    SeasonalRobustZ.name: SeasonalRobustZ,
}
