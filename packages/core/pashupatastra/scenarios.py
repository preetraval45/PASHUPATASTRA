"""Labelled scenarios — the corpus Phase 2 is measured against.

**This is not PIB.** The benchmark proper (`benchmark/README.md`) injects faults
into a running containerized stack, because replaying telemetry is cheaper and
much less credible. These scenarios are telemetry-level replay: they exercise
detection, correlation and recall against known-correct answers, and they cannot
tell you whether the system works on a real stack. Named `scenarios` rather than
`benchmark` so the two are not confused, and so nothing here is ever quoted as a
benchmark result.

**The honest limitation, stated once and loudly.** The roadmap's defence against
self-flattery is that scenarios are authored *before* the logic that resolves
them. That is not true here — detection, correlation and memory already existed
when these were written, so a scenario can be unconsciously shaped to pass. Three
things reduce that, none of them eliminate it:

* **Negative scenarios**, where the correct answer is that nothing happened.
  Without them a system that flags everything scores perfectly.
* **Adversarial scenarios**, written specifically to catch mistakes this
  implementation is known to be capable of — a deploy that is a red herring, two
  unrelated failures in the same minute, a prior incident whose diagnosis was
  wrong. These are the scenarios worth having, because a corpus of cases the code
  obviously handles measures nothing.
* **Failures reported first**, in every summary this module produces.

What remains unmitigated is that one person wrote both the code and the answer
key. That belongs in the paper's threats to validity, not in a footnote.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from .detection import Finding
from .events import (
    AlertPayload,
    DeploymentPayload,
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    LogPayload,
    MetricPayload,
    Provenance,
    Severity,
)

EPOCH = datetime(2026, 1, 1, 12, 0, 0).astimezone()
"""A fixed origin so every scenario is reproducible.

Scenario times are offsets in seconds from here rather than wall-clock stamps: a
corpus whose results change with the date is not a corpus.
"""


class Expectation(StrEnum):
    """What the correct answer is."""

    INCIDENT = "incident"
    """A real incident. The system should detect and correlate it."""

    NOTHING = "nothing"
    """A negative case — benign activity that resembles a problem. The correct
    answer is silence, and a system that cannot stay silent is not usable."""

    ESCALATE = "escalate"
    """Real, but not something the system should resolve alone. Handing off is a
    success outcome, and a benchmark that does not reward it teaches guessing."""


@dataclass
class Signal:
    """One observation in a scenario, as a time offset from the scenario start."""

    at_seconds: float
    entity: str
    kind: str = "metric"
    name: str = "value"
    value: float = 0.0
    message: str | None = None
    version: str | None = None
    anomalous: bool = False
    """Whether this observation is part of the fault, per the answer key. Used to
    score detection without asking the detector what it thinks it found."""


@dataclass
class Baseline:
    """A run of normal samples, expanded into signals on load.

    Exists because the first version of this corpus gave each scenario four or
    five samples and every real incident was missed — not by a bug, but because a
    detector reports `UNKNOWN` until it has enough history, exactly as designed.

    That is an operational constraint, not a test-fixture detail: a detector
    genuinely cannot judge a metric it has just met, and a corpus that ignores
    that measures a system nobody could deploy. Declaring the warm-up explicitly
    keeps it visible instead of burying thirty near-identical lines in YAML.
    """

    entity: str
    name: str
    value: float
    samples: int = 30
    interval_seconds: float = 60.0
    jitter: float = 0.02
    start_seconds: float = 0.0
    drift: float = 0.0
    """Change per sample. Non-zero makes this a trend rather than a flat run —
    needed to express something like a morning traffic ramp honestly, instead of
    faking one with a flat baseline and a step at the end (which is not a ramp,
    and is genuinely anomalous)."""

    def expand(self) -> list[Signal]:
        """Deterministic pseudo-jitter — no RNG, so the corpus never shifts."""
        signals = []
        for index in range(self.samples):
            # A fixed alternating pattern: enough variation that MAD is non-zero,
            # reproducible without seeding anything.
            offset = self.jitter * ((index % 5) - 2) / 2
            signals.append(
                Signal(
                    at_seconds=self.start_seconds + index * self.interval_seconds,
                    entity=self.entity,
                    name=self.name,
                    value=round(self.value + offset + self.drift * index, 6),
                )
            )
        return signals


@dataclass
class Scenario:
    """One labelled case."""

    id: str
    name: str
    category: str
    expectation: Expectation
    signals: list[Signal] = field(default_factory=list)
    root_cause: str | None = None
    """Free text, matched loosely. `None` for negative cases."""

    expected_incidents: int = 1
    """How many distinct incidents the signals represent. `2` is the interesting
    value: it catches a correlator that merges unrelated failures."""

    true_incident_of: dict[str, str] = field(default_factory=dict)
    """entity -> true incident label, for scoring merges and splits."""

    prior_incident: dict[str, Any] | None = None
    """A memory that should (or should not) surface as a precedent."""

    expected_precedent: str | None = None
    notes: str = ""
    difficulty: str = "medium"

    def events(self, origin: datetime = EPOCH) -> list[Event]:
        """Replay the scenario as normalized events."""
        return [self._event(index, signal, origin) for index, signal in enumerate(self.signals)]

    def _event(self, index: int, signal: Signal, origin: datetime) -> Event:
        at = origin + timedelta(seconds=signal.at_seconds)
        kind, entity_id = (
            signal.entity.split(":", 1) if ":" in signal.entity else ("service", signal.entity)
        )
        ref = EntityRef(kind=EntityKind(kind), id=entity_id, name=entity_id)

        match signal.kind:
            case "deployment":
                payload: Any = DeploymentPayload(
                    service=entity_id, version=signal.version or "v0"
                )
                event_class = EventClass.DEPLOYMENT
            case "log":
                payload = LogPayload(message=signal.message or "", level="error")
                event_class = EventClass.LOG
            case "alert":
                payload = AlertPayload(rule_id=signal.name, condition=signal.message or "")
                event_class = EventClass.ALERT
            case _:
                payload = MetricPayload(name=signal.name, value=signal.value)
                event_class = EventClass.METRIC

        return Event(
            id=f"{self.id}-{index:03d}",
            event_class=event_class,
            source="scenario",
            occurred_at=at,
            observed_at=at,
            entity_ref=ref,
            provenance=Provenance(source_system="scenario", query=self.id),
            severity=Severity.WARNING if signal.anomalous else Severity.INFO,
            payload=payload,
        )

    def anomalous_event_ids(self) -> set[str]:
        """The answer key for detection."""
        return {
            f"{self.id}-{index:03d}"
            for index, signal in enumerate(self.signals)
            if signal.anomalous
        }

    def truth_for(self, finding: Finding) -> str:
        """Which true incident a finding belongs to — for merge/split scoring."""
        return self.true_incident_of.get(finding.entity_key, self.id)


# --- loading ------------------------------------------------------------------


def load_scenario(data: dict[str, Any]) -> Scenario:
    """Build a scenario from parsed YAML, failing loudly on a malformed one.

    Strict rather than forgiving: a scenario that silently loses its answer key
    still runs and still produces a number, and that number is worse than no
    number because it looks like a result.
    """
    required = {"id", "name", "category", "expectation", "signals"}
    if missing := required - data.keys():
        raise ValueError(f"scenario missing required field(s): {', '.join(sorted(missing))}")

    expectation = Expectation(data["expectation"])
    root_cause = data.get("root_cause")

    if expectation is Expectation.INCIDENT and not root_cause:
        raise ValueError(f"{data['id']}: an incident scenario must state its root cause")
    if expectation is Expectation.NOTHING and root_cause:
        raise ValueError(
            f"{data['id']}: a negative scenario must not state a root cause — "
            "there is nothing to be right about"
        )

    signals: list[Signal] = []
    for baseline in data.get("baselines", []):
        signals.extend(Baseline(**baseline).expand())
    signals.extend(Signal(**signal) for signal in data["signals"])
    signals.sort(key=lambda signal: signal.at_seconds)

    if not signals:
        raise ValueError(f"{data['id']}: a scenario with no signals tests nothing")

    if expectation is not Expectation.NOTHING and not any(s.anomalous for s in signals):
        raise ValueError(
            f"{data['id']}: an incident scenario must mark which signals are the fault, "
            "or detection cannot be scored against an answer key"
        )

    return Scenario(
        id=data["id"],
        name=data["name"],
        category=data["category"],
        expectation=expectation,
        signals=signals,
        root_cause=root_cause,
        expected_incidents=data.get("expected_incidents", 1),
        true_incident_of=data.get("true_incident_of", {}),
        prior_incident=data.get("prior_incident"),
        expected_precedent=data.get("expected_precedent"),
        notes=data.get("notes", ""),
        difficulty=data.get("difficulty", "medium"),
    )


def load_scenarios(directory: str | Path) -> list[Scenario]:
    """Load every scenario in a directory, sorted by id for reproducibility."""
    path = Path(directory)
    scenarios = [
        load_scenario(yaml.safe_load(file.read_text(encoding="utf-8")))
        for file in sorted(path.glob("*.yaml"))
    ]

    if duplicates := {s.id for s in scenarios if [x.id for x in scenarios].count(s.id) > 1}:
        raise ValueError(f"duplicate scenario id(s): {', '.join(sorted(duplicates))}")
    return scenarios


# --- scoring ------------------------------------------------------------------


@dataclass
class ScenarioResult:
    """One scenario's outcome. Failures are fields, not exceptions."""

    scenario_id: str
    expectation: Expectation
    detected: bool
    incidents_found: int
    incidents_expected: int
    incorrect_merges: int = 0
    incorrect_splits: int = 0
    precedent_found: str | None = None
    precedent_expected: str | None = None
    notes: str = ""

    @property
    def false_alarm(self) -> bool:
        """Flagged something on a scenario where the answer was silence."""
        return self.expectation is Expectation.NOTHING and self.detected

    @property
    def missed(self) -> bool:
        return self.expectation is not Expectation.NOTHING and not self.detected

    @property
    def grouping_correct(self) -> bool:
        return self.incidents_found == self.incidents_expected

    @property
    def precedent_correct(self) -> bool:
        return self.precedent_found == self.precedent_expected

    @property
    def passed(self) -> bool:
        return (
            not self.false_alarm
            and not self.missed
            and self.grouping_correct
            and self.precedent_correct
        )


@dataclass
class CorpusResult:
    """The whole run. `summary()` reports failures before successes."""

    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def false_alarms(self) -> list[ScenarioResult]:
        return [r for r in self.results if r.false_alarm]

    @property
    def missed(self) -> list[ScenarioResult]:
        return [r for r in self.results if r.missed]

    @property
    def mis_grouped(self) -> list[ScenarioResult]:
        return [r for r in self.results if not r.grouping_correct]

    @property
    def false_precedents(self) -> list[ScenarioResult]:
        return [
            r
            for r in self.results
            if r.precedent_found is not None and r.precedent_found != r.precedent_expected
        ]

    @property
    def passed(self) -> list[ScenarioResult]:
        return [r for r in self.results if r.passed]

    def summary(self) -> dict[str, object]:
        """Failures first, deliberately.

        A summary that leads with a pass rate is read as a pass rate. The
        roadmap's rule — false remediation before autonomous resolution — applies
        to every table this project produces, including this one.
        """
        return {
            "false_alarms": len(self.false_alarms),
            "missed": len(self.missed),
            "mis_grouped": len(self.mis_grouped),
            "false_precedents": len(self.false_precedents),
            "passed": len(self.passed),
            "total": len(self.results),
        }
