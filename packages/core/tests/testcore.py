"""Schema round-trips, hypothesis evidence rule, and topology semantics."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from pashupatastra import (
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Hypothesis,
    Incident,
    IncidentSeverity,
    IncidentState,
    Node,
    Provenance,
    TopologyGraph,
    incident_id,
)
from pashupatastra.events import DeploymentPayload, MetricPayload
from pashupatastra.topology import Edge


def _ref(kind: EntityKind, name: str) -> EntityRef:
    return EntityRef(kind=kind, id=name, name=name)


def _event() -> Event:
    now = datetime.now().astimezone()
    return Event(
        event_class=EventClass.METRIC,
        source="prometheus",
        occurred_at=now - timedelta(seconds=5),
        observed_at=now,
        entity_ref=_ref(EntityKind.DATABASE, "postgres"),
        payload=MetricPayload(name="pg_connections_pct", value=98.0, unit="percent"),
        provenance=Provenance(source_system="amp", query="pg_connections_pct"),
    )


def test_event_round_trip_preserves_payload_type() -> None:
    event = _event()
    restored = Event.model_validate_json(event.model_dump_json())
    assert isinstance(restored.payload, MetricPayload)
    assert restored.payload.value == 98.0
    assert restored.id == event.id


def test_deployment_payload_round_trip() -> None:
    now = datetime.now().astimezone()
    event = Event(
        event_class=EventClass.DEPLOYMENT,
        source="github-actions",
        occurred_at=now,
        observed_at=now,
        entity_ref=_ref(EntityKind.SERVICE, "checkout-api"),
        payload=DeploymentPayload(service="checkout-api", version="v4.21", previous_version="v4.20"),
        provenance=Provenance(source_system="github", url="https://example.invalid/run/1"),
    )
    restored = Event.model_validate_json(event.model_dump_json())
    assert isinstance(restored.payload, DeploymentPayload)
    assert restored.payload.previous_version == "v4.20"


def test_ingestion_lag_is_positive() -> None:
    assert _event().ingestion_lag_seconds == pytest.approx(5.0, abs=0.5)


def test_hypothesis_without_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(statement="the database is sad", confidence=0.9, evidence=[])


def test_blast_radius_follows_dependents() -> None:
    graph = TopologyGraph()
    for kind, name, users in [
        (EntityKind.DATABASE, "postgres", 0),
        (EntityKind.SERVICE, "api", 0),
        (EntityKind.SERVICE, "frontend", 1200),
        (EntityKind.CACHE, "redis", 0),
    ]:
        graph.add_node(Node(ref=_ref(kind, name), estimated_users=users))

    graph.add_edge(Edge(source="service:api", target="database:postgres"))
    graph.add_edge(Edge(source="service:frontend", target="service:api"))
    graph.add_edge(Edge(source="service:api", target="cache:redis"))

    radius = graph.blast_radius("database:postgres")
    assert set(radius.affected) == {"service:api", "service:frontend"}
    assert radius.estimated_users == 1200
    assert "cache:redis" not in radius.affected


def test_unconnected_entities_are_not_adjacent() -> None:
    graph = TopologyGraph()
    graph.add_node(Node(ref=_ref(EntityKind.SERVICE, "billing")))
    graph.add_node(Node(ref=_ref(EntityKind.SERVICE, "search")))
    assert not graph.adjacent("service:billing", "service:search")


def test_incident_transitions_are_appended_with_actor() -> None:
    incident = Incident(
        id=incident_id(2026, 810),
        severity=IncidentSeverity.CRITICAL,
        opened_at=datetime.now().astimezone(),
    )
    incident.transition_to(IncidentState.CORRELATED, "agent:incident", "3 events, adjacent")
    incident.transition_to(IncidentState.DIAGNOSED, "agent:incident", "deployment correlated")

    assert incident.state is IncidentState.DIAGNOSED
    assert [t.to_state for t in incident.transitions] == [
        IncidentState.CORRELATED,
        IncidentState.DIAGNOSED,
    ]
    assert incident.transitions[0].from_state is IncidentState.DETECTED


def test_human_involvement_disqualifies_autonomous_resolution() -> None:
    incident = Incident(
        id=incident_id(2026, 811),
        severity=IncidentSeverity.HIGH,
        opened_at=datetime.now().astimezone(),
    )
    incident.transition_to(IncidentState.CORRELATED, "agent:incident", "correlated")
    incident.transition_to(IncidentState.RESOLVED, "human:preet", "approved rollback")
    assert not incident.resolved_autonomously
