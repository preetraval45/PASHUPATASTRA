"""Detection.

The rule under most scrutiny here is deference: when an upstream alert already
covers a signal, detecting it again produces two findings for one fact, and
downstream that reads as two independent signals agreeing.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from pashupatastra import EntityKind, EntityRef, Event, EventClass, Provenance, Severity
from pashupatastra.detection import Detector, UpstreamRules
from pashupatastra.events import AlertPayload, MetricPayload

NOW = datetime.now(timezone.utc)


def metric(name: str, value: float, entity: str = "api", at_offset: int = 0) -> Event:
    return Event(
        event_class=EventClass.METRIC,
        source="prometheus",
        occurred_at=NOW + timedelta(seconds=at_offset),
        observed_at=NOW,
        entity_ref=EntityRef(kind=EntityKind.SERVICE, id=entity, name=entity),
        payload=MetricPayload(name=name, value=value),
        provenance=Provenance(source_system="prometheus", query=name),
    )


def alert(rule: str, entity: str = "api", state: str = "firing") -> Event:
    return Event(
        event_class=EventClass.ALERT,
        source="prometheus",
        occurred_at=NOW,
        observed_at=NOW,
        entity_ref=EntityRef(kind=EntityKind.SERVICE, id=entity, name=entity),
        severity=Severity.CRITICAL,
        payload=AlertPayload(
            rule_id=rule, condition="rate > 0.05", upstream_state=state
        ),
        provenance=Provenance(source_system="prometheus", query=rule),
    )


def warm(detector: Detector, name: str = "cpu", entity: str = "api", n: int = 60) -> None:
    random.seed(5)
    detector.process([metric(name, 40 + random.uniform(-2, 2), entity) for _ in range(n)])


def test_no_findings_while_cold() -> None:
    """Silence from an unwarmed detector is honest; a confident 'normal' is not."""
    detector = Detector()
    assert detector.process([metric("cpu", 95.0)]) == []


def test_spike_produces_a_finding_once_warm() -> None:
    detector = Detector()
    warm(detector)
    findings = detector.process([metric("cpu", 95.0)])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.entity_key == "service:api"
    assert finding.direction == "high"
    assert finding.source == "baseline"
    assert finding.deviation > 3


def test_findings_cite_the_event_that_produced_them() -> None:
    """A finding that cannot be traced back is unusable downstream — a
    hypothesis built on it could not carry the citation."""
    detector = Detector()
    warm(detector)
    event = metric("cpu", 95.0)
    finding = detector.process([event])[0]
    assert finding.evidence == [event.id]


def test_upstream_alert_becomes_a_finding() -> None:
    detector = Detector()
    findings = detector.process([alert("HighErrorRate")])
    assert len(findings) == 1
    assert findings[0].source == "upstream:HighErrorRate"
    assert findings[0].severity is Severity.CRITICAL


def test_resolved_alerts_do_not_produce_findings() -> None:
    detector = Detector()
    assert detector.process([alert("HighErrorRate", state="resolved")]) == []


def test_detection_defers_to_an_upstream_rule() -> None:
    """Two findings for one fact would look like corroboration downstream —
    two independent signals agreeing — when it is one signal counted twice."""
    detector = Detector()
    warm(detector, name="HighErrorRate")

    findings = detector.process([alert("HighErrorRate"), metric("HighErrorRate", 95.0)])

    assert len(findings) == 1
    assert findings[0].source == "upstream:HighErrorRate"


def test_deference_applies_within_the_same_batch() -> None:
    """The alert and the metric it duplicates usually arrive together."""
    detector = Detector()
    warm(detector, name="HighErrorRate")
    findings = detector.process([metric("HighErrorRate", 95.0), alert("HighErrorRate")])
    assert [f.source for f in findings] == ["upstream:HighErrorRate"]


def test_deference_is_scoped_to_the_claimed_signal() -> None:
    """An upstream rule owning error rate must not silence CPU detection."""
    detector = Detector()
    warm(detector, name="cpu")
    findings = detector.process([alert("HighErrorRate"), metric("cpu", 95.0)])

    sources = {f.source for f in findings}
    assert "upstream:HighErrorRate" in sources
    assert "baseline" in sources


def test_deference_is_scoped_to_the_claimed_entity() -> None:
    detector = Detector()
    warm(detector, name="errors", entity="billing")
    findings = detector.process(
        [alert("errors", entity="api"), metric("errors", 95.0, entity="billing")]
    )
    assert any(f.entity_key == "service:billing" and f.source == "baseline" for f in findings)


def test_deferred_signals_still_train_the_baseline() -> None:
    """The baseline stays useful for context, and for the day the upstream rule
    is removed."""
    detector = Detector()
    detector.process([alert("cpu")])
    for _ in range(60):
        detector.process([metric("cpu", 40.0)])

    assert len(detector.baselines.baseline("service:api", "cpu")) == 60


def test_extreme_deviation_is_critical() -> None:
    detector = Detector()
    warm(detector)
    finding = detector.process([metric("cpu", 500.0)])[0]
    assert finding.severity is Severity.CRITICAL


def test_moderate_deviation_is_a_warning() -> None:
    """Severity here is crude on purpose: what a deviation *means* depends on
    blast radius and recent changes, and that is correlation's job.

    The value is derived from the baseline's own spread rather than hardcoded —
    against a metric that never moves more than ±2, even 52 is extreme, and a
    fixed number would be testing the fixture instead of the rule.
    """
    detector = Detector()
    warm(detector)

    baseline = detector.baselines.baseline("service:api", "cpu")
    just_over = (baseline.median or 0) + 4.0 * (baseline.mad or 1.0)

    finding = detector.process([metric("cpu", just_over)])[0]
    assert 3 <= abs(finding.deviation) < 6
    assert finding.severity is Severity.WARNING


def test_warmup_is_reportable() -> None:
    detector = Detector()
    warm(detector)
    detector.process([alert("HighErrorRate")])

    state = detector.warmup()
    assert state["warm"] == 1
    assert state["upstream_rules"] == 1


def test_description_is_human_readable() -> None:
    detector = Detector()
    warm(detector)
    finding = detector.process([metric("cpu", 95.0)])[0]
    text = finding.describe()
    assert "cpu" in text and "service:api" in text and "high" in text


def test_rules_registry_reports_ownership() -> None:
    rules = UpstreamRules()
    assert rules.owner("service:api", "cpu") is None
    rules.claim("service:api", "cpu", "HighCPU")
    assert rules.owner("service:api", "cpu") == "HighCPU"
