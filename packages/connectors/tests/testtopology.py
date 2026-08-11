"""Topology construction.

The strictness about edges is the thing under test. A fabricated edge inflates
blast radius, which inflates risk, which changes what the system is allowed to
do on its own — so "we saw these two together" must never become an edge.
"""

from __future__ import annotations

from datetime import datetime

from drishti.topology import TopologyBuilder
from pashupatastra import EntityKind, EntityRef, Event, EventClass, Provenance
from pashupatastra.events import MetricPayload, TracePayload


def _ref(kind: EntityKind, name: str) -> EntityRef:
    return EntityRef(kind=kind, id=name, name=name)


def _event(kind: EntityKind, name: str, payload, event_class: EventClass) -> Event:
    now = datetime.now().astimezone()
    return Event(
        event_class=event_class,
        source="test",
        occurred_at=now,
        observed_at=now,
        entity_ref=_ref(kind, name),
        payload=payload,
        provenance=Provenance(source_system="test"),
    )


def metric(name: str, kind: EntityKind = EntityKind.SERVICE) -> Event:
    return _event(kind, name, MetricPayload(name="cpu", value=1.0), EventClass.METRIC)


def trace(hops: list[str]) -> Event:
    return _event(
        EntityKind.SERVICE,
        hops[0] if hops else "unknown",
        TracePayload(trace_id="t1", span_id="s1", duration_ms=12.0, status="ok", service_hops=hops),
        EventClass.TRACE,
    )


def test_every_event_contributes_a_node() -> None:
    delta = TopologyBuilder().build([metric("api"), metric("postgres", EntityKind.DATABASE)])
    assert {n.ref.key() for n in delta.node_list} == {"service:api", "database:postgres"}


def test_metrics_alone_create_no_edges() -> None:
    """Two services emitting metrics at the same moment is not a dependency."""
    delta = TopologyBuilder().build([metric("api"), metric("billing"), metric("search")])
    assert delta.edge_list == []


def test_trace_hops_become_dependency_edges() -> None:
    delta = TopologyBuilder().build([trace(["frontend", "api", "postgres"])])
    edges = {(e.source, e.target) for e in delta.edge_list}
    assert edges == {
        ("service:frontend", "service:api"),
        ("service:api", "service:postgres"),
    }


def test_edge_direction_is_caller_depends_on_callee() -> None:
    """frontend called api, so frontend breaks when api does — not the reverse."""
    delta = TopologyBuilder().build([trace(["frontend", "api"])])
    edge = delta.edge_list[0]
    assert edge.source == "service:frontend"
    assert edge.target == "service:api"


def test_self_calls_are_not_dependencies() -> None:
    delta = TopologyBuilder().build([trace(["api", "api", "postgres"])])
    assert {(e.source, e.target) for e in delta.edge_list} == {
        ("service:api", "service:postgres")
    }


def test_repeated_traces_do_not_duplicate_edges() -> None:
    builder = TopologyBuilder()
    delta = builder.build([trace(["frontend", "api"]), trace(["frontend", "api"])])
    assert len(delta.edge_list) == 1


def test_merge_keeps_the_richer_user_estimate() -> None:
    """A connector blind to user counts must not erase another's reading."""
    first = TopologyBuilder().build([metric("frontend")])
    first.nodes["service:frontend"].estimated_users = 1200

    second = TopologyBuilder().build([metric("frontend")])
    merged = first.merge(second)
    assert merged.nodes["service:frontend"].estimated_users == 1200


def test_declared_dependencies_are_honoured() -> None:
    """The escape hatch for dependencies no telemetry reveals."""
    delta = TopologyBuilder.declared({"service:cron": ["database:postgres", "cache:redis"]})
    assert {(e.source, e.target) for e in delta.edge_list} == {
        ("service:cron", "database:postgres"),
        ("service:cron", "cache:redis"),
    }


def test_declared_map_parses_bare_names_as_services() -> None:
    delta = TopologyBuilder.declared({"checkout": ["api"]})
    assert {n.ref.key() for n in delta.node_list} == {"service:checkout", "service:api"}


def test_edges_are_not_drawn_to_undependable_kinds() -> None:
    """A host is not something a service 'depends on' in the blast-radius sense."""
    delta = TopologyBuilder.declared({"service:api": ["host:node-1"]})
    assert delta.edge_list == []
    assert "host:node-1" in delta.nodes, "the node still exists, only the edge is refused"
