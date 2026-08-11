"""Statistical baselines per metric and entity.

**Robust statistics, not mean and standard deviation.** The obvious baseline is
a rolling mean with a z-score, and it fails in exactly the situation that
matters: the incident itself poisons the baseline. A ten-minute outage pulls the
mean up and inflates the standard deviation, so by the time an operator looks,
the anomaly has taught the detector that it is normal — and the second
occurrence scores lower than the first.

Median and MAD (median absolute deviation) do not move much when a minority of
samples go wild, so a metric that spikes still reads as a spike, and the
recovery still reads as a recovery.

**A baseline that has not seen enough data reports "unknown", never "normal".**
Those are different claims. Silence from an unwarmed detector is honest; a
confident "within range" from four samples is not, and it is the kind of
statement that gets an incident closed early.

No cloud, no model, no training step — this runs on a laptop and is part of the
open-source core (Platform ADR).
"""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

# 0.6745 is the 75th percentile of the standard normal. Dividing MAD by it makes
# the result comparable to a standard deviation for normally-distributed data,
# so thresholds keep their familiar meaning ("3 sigma") without the fragility.
_MAD_TO_SIGMA = 0.6745

MIN_SAMPLES = 20
"""Below this the baseline reports `UNKNOWN`. Twenty is not a statistical
guarantee — it is the point past which a median stops being an accident of the
first few readings."""

DEFAULT_WINDOW = 200


class Band(StrEnum):
    UNKNOWN = "unknown"
    """Not enough history to judge. Distinct from `NORMAL`, deliberately."""

    NORMAL = "normal"
    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True)
class Reading:
    """What the baseline says about one observation."""

    band: Band
    value: float
    median: float | None
    deviation: float
    """Robust z-score: how many MAD-derived sigmas from the median. Zero when
    unknown."""
    samples: int

    @property
    def is_anomalous(self) -> bool:
        return self.band in (Band.HIGH, Band.LOW)

    @property
    def confidence(self) -> float:
        """0–1, and it climbs with both deviation and sample count.

        A 4-sigma reading from 25 samples is a weaker claim than the same
        deviation from 200, and the number that reaches a risk score should say
        so — diagnostic confidence feeds effective risk, so overstating it here
        would quietly widen what the system is allowed to do.
        """
        if self.band is Band.UNKNOWN:
            return 0.0
        magnitude = min(abs(self.deviation) / 6.0, 1.0)
        evidence = min(self.samples / (MIN_SAMPLES * 5), 1.0)
        return round(magnitude * (0.5 + 0.5 * evidence), 3)


@dataclass
class Baseline:
    """Rolling robust statistics for one (entity, metric) pair."""

    key: str
    window: int = DEFAULT_WINDOW
    threshold: float = 3.0
    _samples: deque[float] = field(default_factory=deque, init=False)

    def __post_init__(self) -> None:
        self._samples = deque(maxlen=self.window)

    def __len__(self) -> int:
        return len(self._samples)

    @property
    def median(self) -> float | None:
        return statistics.median(self._samples) if self._samples else None

    @property
    def mad(self) -> float | None:
        """Median absolute deviation, scaled to be comparable with a sigma."""
        if len(self._samples) < 2:
            return None
        median = statistics.median(self._samples)
        deviations = [abs(x - median) for x in self._samples]
        return statistics.median(deviations) / _MAD_TO_SIGMA

    def evaluate(self, value: float) -> Reading:
        """Judge a value **without** learning it. Observation is a separate,
        explicit step so a caller cannot accidentally teach the baseline that an
        incident is normal in the act of detecting it."""
        if len(self._samples) < MIN_SAMPLES:
            return Reading(Band.UNKNOWN, value, self.median, 0.0, len(self._samples))

        median = statistics.median(self._samples)
        spread = self.mad or 0.0

        if spread == 0:
            # A flat metric. Any change is real but unmeasurable in sigmas, so
            # it is reported as a deviation of exactly the threshold rather than
            # infinity — enough to flag, not enough to dominate a ranking.
            if value == median:
                return Reading(Band.NORMAL, value, median, 0.0, len(self._samples))
            band = Band.HIGH if value > median else Band.LOW
            return Reading(band, value, median, self.threshold, len(self._samples))

        deviation = (value - median) / spread
        if abs(deviation) < self.threshold:
            band = Band.NORMAL
        else:
            band = Band.HIGH if deviation > 0 else Band.LOW
        return Reading(band, value, median, round(deviation, 3), len(self._samples))

    def observe(self, value: float) -> None:
        """Add a sample to the history."""
        self._samples.append(value)

    def evaluate_and_observe(self, value: float) -> Reading:
        """Judge, then learn.

        In this order for a reason: judging first means the current value never
        contributes to the baseline it is being measured against, so a single
        extreme reading cannot partially normalize itself.
        """
        reading = self.evaluate(value)
        self.observe(value)
        return reading


class BaselineStore:
    """Baselines keyed by entity and metric.

    Kept per pair rather than per metric: 90% CPU is unremarkable on a batch
    worker and alarming on an API pod, and a shared baseline would learn the
    average of two populations that have nothing to do with each other.
    """

    def __init__(self, window: int = DEFAULT_WINDOW, threshold: float = 3.0) -> None:
        self.window = window
        self.threshold = threshold
        self._baselines: dict[str, Baseline] = {}

    def key(self, entity_key: str, metric: str) -> str:
        return f"{entity_key}|{metric}"

    def baseline(self, entity_key: str, metric: str) -> Baseline:
        key = self.key(entity_key, metric)
        if key not in self._baselines:
            self._baselines[key] = Baseline(
                key=key, window=self.window, threshold=self.threshold
            )
        return self._baselines[key]

    def evaluate_and_observe(self, entity_key: str, metric: str, value: float) -> Reading:
        return self.baseline(entity_key, metric).evaluate_and_observe(value)

    def __len__(self) -> int:
        return len(self._baselines)

    @property
    def warm(self) -> int:
        """How many baselines can actually judge. Worth surfacing: a system that
        has been up for five minutes knows nothing yet, and its silence should
        not be read as an all-clear."""
        return sum(1 for b in self._baselines.values() if len(b) >= MIN_SAMPLES)
