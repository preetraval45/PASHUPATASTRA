"""Anomaly detection and alert ingestion.

Statistical first. An ML detector earns its place only by beating the baseline
on the benchmark — not by being more interesting — because a model that cannot
explain itself produces findings the reasoning layer cannot cite, and an
uncitable finding is suppressed anyway (Grounding ADR).

**Detection defers to upstream rules rather than competing with them.** If
Prometheus already alerts on `HighErrorRate` for a service, this system
ingesting that alert *and* independently flagging the same metric produces two
findings for one fact. Downstream that looks like corroboration — two
independent signals agreeing — when it is one signal counted twice, and
correlation would treat it as stronger evidence than it is.

So an upstream rule claims a (entity, metric) pair, and detection stands down
for it. The upstream alert is still ingested; it simply is not seconded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .baselines import Band, BaselineStore, Reading
from .events import Event, EventClass, Severity
from .events import AlertPayload, MetricPayload


@dataclass(frozen=True)
class Finding:
    """A detected deviation, with everything needed to cite it.

    `evidence` holds the event IDs that produced this finding, so a hypothesis
    built on it can carry the citation all the way to the operator. A finding
    that cannot be traced back is not usable downstream.
    """

    entity_key: str
    signal: str
    at: datetime
    value: float
    baseline: float | None
    deviation: float
    direction: str
    """`high` or `low`."""
    confidence: float
    source: str
    """`baseline` for statistical detection, or the upstream rule's identity."""
    evidence: list[str] = field(default_factory=list)
    severity: Severity = Severity.WARNING

    @property
    def key(self) -> str:
        return f"{self.entity_key}|{self.signal}"

    def describe(self) -> str:
        if self.baseline is None:
            return f"{self.signal} on {self.entity_key} is {self.value:g} ({self.source})"
        return (
            f"{self.signal} on {self.entity_key} is {self.value:g}, "
            f"{abs(self.deviation):.1f}σ {self.direction} its usual {self.baseline:g}"
        )


class UpstreamRules:
    """Which (entity, metric) pairs an external alerting system already owns.

    Registered from ingested alert events, so the deference is automatic: the
    moment Prometheus fires `HighErrorRate` for checkout-api, this system stops
    independently flagging that service's error rate.
    """

    def __init__(self) -> None:
        self._claimed: dict[str, str] = {}

    def claim(self, entity_key: str, signal: str, rule_id: str) -> None:
        self._claimed[f"{entity_key}|{signal}"] = rule_id

    def owner(self, entity_key: str, signal: str) -> str | None:
        return self._claimed.get(f"{entity_key}|{signal}")

    def claims(self) -> dict[str, str]:
        return dict(self._claimed)


class Detector:
    """Turns a stream of events into findings."""

    def __init__(
        self,
        baselines: BaselineStore | None = None,
        upstream: UpstreamRules | None = None,
    ) -> None:
        self.baselines = baselines or BaselineStore()
        self.upstream = upstream or UpstreamRules()

    def process(self, events: list[Event]) -> list[Finding]:
        findings: list[Finding] = []

        # Alerts first, so a rule registered in this batch already suppresses
        # duplicate statistical detection within the same batch rather than
        # only from the next one.
        for event in events:
            if event.event_class is EventClass.ALERT:
                findings.extend(self._from_alert(event))

        for event in events:
            if event.event_class is EventClass.METRIC:
                findings.extend(self._from_metric(event))

        return findings

    def _from_alert(self, event: Event) -> list[Finding]:
        payload = event.payload
        if not isinstance(payload, AlertPayload):
            return []

        entity_key = event.entity_ref.key()
        # The rule now owns this signal; statistical detection stands down.
        self.upstream.claim(entity_key, payload.rule_id, payload.rule_id)

        state = (payload.upstream_state or "firing").lower()
        if state in {"resolved", "ok", "inactive"}:
            return []

        return [
            Finding(
                entity_key=entity_key,
                signal=payload.rule_id,
                at=event.occurred_at,
                value=1.0,
                baseline=None,
                deviation=0.0,
                direction="high",
                # An upstream rule is a human-authored assertion that this
                # condition matters. It is not more *certain* than statistics —
                # thresholds are guesses too — but it is intentional, so it is
                # trusted more than an unexplained deviation.
                confidence=0.7,
                source=f"upstream:{payload.rule_id}",
                evidence=[event.id],
                severity=event.severity or Severity.WARNING,
            )
        ]

    def _from_metric(self, event: Event) -> list[Finding]:
        payload = event.payload
        if not isinstance(payload, MetricPayload):
            return []

        entity_key = event.entity_ref.key()
        signal = payload.name

        owner = self.upstream.owner(entity_key, signal)
        if owner is not None:
            # Still learn from the sample — the baseline stays useful for
            # context and for the day the upstream rule is removed — but do not
            # emit a second finding for a fact already reported.
            self.baselines.baseline(entity_key, signal).observe(payload.value)
            return []

        reading = self.baselines.evaluate_and_observe(entity_key, signal, payload.value)
        if not reading.is_anomalous:
            return []

        return [
            Finding(
                entity_key=entity_key,
                signal=signal,
                at=event.occurred_at,
                value=reading.value,
                baseline=reading.median,
                deviation=reading.deviation,
                direction="high" if reading.band is Band.HIGH else "low",
                confidence=reading.confidence,
                source="baseline",
                evidence=[event.id],
                severity=_severity_for(reading),
            )
        ]

    def warmup(self) -> dict[str, int]:
        """How much of the detector can actually judge yet.

        Surfaced because an unwarmed detector's silence must not be mistaken for
        an all-clear — the same reason a failed connector is reported rather
        than passed over.
        """
        return {
            "baselines": len(self.baselines),
            "warm": self.baselines.warm,
            "upstream_rules": len(self.upstream.claims()),
        }


def _severity_for(reading: Reading) -> Severity:
    """Deviation alone decides severity here.

    Deliberately crude: what a deviation *means* depends on the entity, the
    blast radius, and whether a deployment just landed — and all of that is
    correlation's job. A detector that tried to rank importance would be making
    a reasoning decision with none of the context needed to make it.
    """
    return Severity.CRITICAL if abs(reading.deviation) >= 6.0 else Severity.WARNING
