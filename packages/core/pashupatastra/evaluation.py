"""Detector evaluation.

Turns "beats the baseline" into a number, so the ML decision in the roadmap is
settled by measurement rather than by whoever argues longest.

Three metrics, and the third is the one usually left out:

  **precision** — of everything flagged, how much was real. Low precision is
  how a detector gets ignored, and an ignored detector has negative value: it
  trains operators that alerts are noise.

  **recall** — of everything real, how much was caught.

  **lead time** — how long *before* the labelled incident it fired. A detector
  with perfect precision and recall that fires at minute nine of a ten-minute
  outage has told the operator nothing they did not already know. Accuracy
  without lead time is a post-mortem, not a detector.

Scoring is per *episode*, not per sample. A 30-minute outage is one thing that
happened; counting each of its 360 samples as a separate catch would let a
detector look excellent by firing continuously through one long incident while
missing every short one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .baselines import Band


@dataclass
class Series:
    """A labelled metric series.

    `anomalies` marks the index ranges that are genuinely incidents. Labels come
    from the scenario definition, authored before the detector — the same rule
    the benchmark follows, and for the same reason.
    """

    name: str
    values: list[float]
    anomalies: list[tuple[int, int]] = field(default_factory=list)
    """Inclusive-exclusive index ranges."""

    def is_anomalous(self, index: int) -> bool:
        return any(start <= index < end for start, end in self.anomalies)

    def episode(self, index: int) -> int | None:
        for episode, (start, end) in enumerate(self.anomalies):
            if start <= index < end:
                return episode
        return None


@dataclass
class Score:
    strategy: str
    series: str
    true_positives: int = 0
    false_positives: int = 0
    missed_episodes: int = 0
    caught_episodes: int = 0
    total_episodes: int = 0
    lead_samples: list[int] = field(default_factory=list)
    warmup_samples: int = 0

    @property
    def precision(self) -> float:
        flagged = self.true_positives + self.false_positives
        return round(self.true_positives / flagged, 3) if flagged else 0.0

    @property
    def recall(self) -> float:
        """Episode recall, not sample recall — one outage is one thing caught."""
        return (
            round(self.caught_episodes / self.total_episodes, 3)
            if self.total_episodes
            else 0.0
        )

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return round(2 * p * r / (p + r), 3) if (p + r) else 0.0

    @property
    def mean_lead(self) -> float:
        """Samples between the first flag and the episode's end. Higher is
        earlier."""
        return (
            round(sum(self.lead_samples) / len(self.lead_samples), 1)
            if self.lead_samples
            else 0.0
        )

    @property
    def false_alarms_per_1000(self) -> float:
        """The number an operator actually feels."""
        total = self.true_positives + self.false_positives + self.warmup_samples
        return round(1000 * self.false_positives / total, 2) if total else 0.0

    def row(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "series": self.series,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "mean_lead": self.mean_lead,
            "false_alarms_per_1000": self.false_alarms_per_1000,
            "caught": f"{self.caught_episodes}/{self.total_episodes}",
        }


def evaluate(strategy, series: Series) -> Score:
    """Run one strategy over one labelled series, online.

    Online because that is how it will run in production: each value is judged
    with only the past available. A strategy scored on the whole series at once
    would be measuring something the system can never do.
    """
    score = Score(
        strategy=getattr(strategy, "name", type(strategy).__name__),
        series=series.name,
        total_episodes=len(series.anomalies),
    )
    first_flag: dict[int, int] = {}

    for index, value in enumerate(series.values):
        reading = strategy.evaluate_and_observe(value)

        if reading.band is Band.UNKNOWN:
            # Warm-up is not credited or penalised. A detector that has not seen
            # enough data has not made a claim, and scoring its silence as a
            # miss would reward strategies that guess early.
            score.warmup_samples += 1
            continue

        episode = series.episode(index)
        if reading.is_anomalous:
            if episode is None:
                score.false_positives += 1
            else:
                score.true_positives += 1
                first_flag.setdefault(episode, index)

    score.caught_episodes = len(first_flag)
    score.missed_episodes = score.total_episodes - score.caught_episodes
    for episode, flagged_at in first_flag.items():
        _, end = series.anomalies[episode]
        score.lead_samples.append(end - flagged_at)

    return score


def compare(strategies: list, series_list: list[Series]) -> list[dict[str, object]]:
    """Score every strategy on every series.

    A fresh strategy instance per series, because carrying learned state between
    unrelated series would let one strategy benefit from an ordering another did
    not get.
    """
    rows: list[dict[str, object]] = []
    for factory in strategies:
        for series in series_list:
            rows.append(evaluate(factory(), series).row())
    return rows


def winner(rows: list[dict[str, object]], metric: str = "f1") -> str | None:
    """Which strategy wins overall, by mean of `metric` across all series.

    Mean across series rather than pooled, so a strategy cannot win by being
    excellent on the one longest series and useless on the rest.
    """
    if not rows:
        return None
    totals: dict[str, list[float]] = {}
    for row in rows:
        totals.setdefault(str(row["strategy"]), []).append(float(row[metric]))
    return max(totals, key=lambda s: sum(totals[s]) / len(totals[s]))
