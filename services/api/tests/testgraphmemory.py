"""Tests for the in-memory topology mirror and the corpus seed.

`testgraph.py` asserts the Postgres store reproduces the semantics `TopologyGraph`
defines. This asserts the same of the fallback, for the same reason: a deployment
without a database still answers blast-radius questions, and risk scoring
consumes those answers without knowing which store produced them.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from app.graphmemory import MemoryGraph
from app.seed import DEMO_EDGES, seed
from pashupatastra import Edge, EntityKind, EntityRef, Node
from pashupatastra.events import (
    EventClass,
    MetricPayload,
    Provenance,
    Severity,
)
from pashupatastra.events import Event
from pashupatastra.topology import TopologyGraph

NOW = datetime(2026, 8, 19, 12, 0, 0).astimezone()


def node(key: str, users: int = 0) -> Node:
    kind, _, entity_id = key.partition(":")
    return Node(
        ref=EntityRef(kind=EntityKind(kind), id=entity_id, name=entity_id),
        estimated_users=users,
    )


def metric(key: str, severity: Severity | None, at: datetime, event_id: str) -> Event:
    kind, _, entity_id = key.partition(":")
    return Event(
        id=event_id,
        event_class=EventClass.METRIC,
        source="test",
        occurred_at=at,
        observed_at=at,
        entity_ref=EntityRef(kind=EntityKind(kind), id=entity_id, name=entity_id),
        severity=severity,
        payload=MetricPayload(name="saturation", value=0.9),
        provenance=Provenance(source_system="test"),
    )


@pytest.fixture
def graph() -> MemoryGraph:
    g = MemoryGraph()
    g.upsert_nodes([node("service:a"), node("service:b", 100), node("database:d", 5)])
    g.upsert_edges([Edge(source="service:a", target="service:b"),
                    Edge(source="service:b", target="database:d")])
    return g


# --- agreement with the reference implementation -----------------------------


def test_blast_radius_matches_the_reference_graph(graph: MemoryGraph) -> None:
    reference = TopologyGraph()
    for key, users in (("service:a", 0), ("service:b", 100), ("database:d", 5)):
        reference.add_node(node(key, users))
    reference.add_edge(Edge(source="service:a", target="service:b"))
    reference.add_edge(Edge(source="service:b", target="database:d"))

    for origin in ("database:d", "service:b", "service:a"):
        assert graph.blast_radius(origin) == reference.blast_radius(origin)


def test_blast_radius_reaches_transitive_dependents(graph: MemoryGraph) -> None:
    """A blast radius that stops at one hop understates impact, which lowers
    effective risk and hands an action more autonomy than it should have."""
    radius = graph.blast_radius("database:d")
    assert radius.affected == ["service:a", "service:b"]
    assert radius.estimated_users == 100


def test_adjacency_is_symmetric(graph: MemoryGraph) -> None:
    assert graph.adjacent("service:a", "database:d")
    assert graph.adjacent("database:d", "service:a")
    assert not graph.adjacent("service:a", "service:unrelated")


# --- severity rollup ----------------------------------------------------------


def test_severity_is_the_worst_in_the_window_not_the_latest(graph: MemoryGraph) -> None:
    """A service that went critical and then reported info is flapping, and the
    newest reading would hide the incident behind its own recovery."""
    graph.save_events([
        metric("service:a", Severity.CRITICAL, NOW - timedelta(minutes=5), "e1"),
        metric("service:a", Severity.INFO, NOW - timedelta(minutes=1), "e2"),
    ])
    assert graph.severity("service:a", now=NOW) == "critical"


def test_severity_ignores_events_outside_the_window(graph: MemoryGraph) -> None:
    graph.save_events([metric("service:a", Severity.CRITICAL, NOW - timedelta(hours=2), "e1")])
    assert graph.severity("service:a", now=NOW) is None


def test_severity_is_none_for_a_silent_entity(graph: MemoryGraph) -> None:
    assert graph.severity("service:b", now=NOW) is None


# --- projections --------------------------------------------------------------


def test_snapshot_omits_edges_whose_endpoints_were_truncated(graph: MemoryGraph) -> None:
    """An edge pointing at a node the client did not receive renders as a line
    to nowhere."""
    snapshot = graph.snapshot(limit=1)
    assert len(snapshot["nodes"]) == 1
    included = {n["key"] for n in snapshot["nodes"]}
    assert all(e["source"] in included and e["target"] in included for e in snapshot["edges"])


def test_counts_track_upserts(graph: MemoryGraph) -> None:
    assert graph.counts() == (3, 2)
    graph.upsert_nodes([node("service:a")])
    assert graph.counts() == (3, 2), "upserting an existing node must not duplicate it"


def test_an_upsert_without_a_user_count_does_not_erase_one(graph: MemoryGraph) -> None:
    """A connector that cannot see user counts must not zero out what another
    connector established — the rule the upsert SQL enforces with its CASE."""
    graph.upsert_nodes([node("service:b", 0)])
    assert graph.entity("service:b")["estimated_users"] == 100


def test_entity_events_are_newest_first_and_capped(graph: MemoryGraph) -> None:
    graph.save_events([
        metric("service:a", Severity.INFO, NOW - timedelta(minutes=i), f"e{i}")
        for i in range(5)
    ])
    events = graph.entity_events("service:a", limit=3)
    assert [e["id"] for e in events] == ["e0", "e1", "e2"]


def test_entity_is_none_when_unknown(graph: MemoryGraph) -> None:
    assert graph.entity("service:never-seen") is None


# --- the corpus seed ----------------------------------------------------------


def test_seed_loads_the_corpus_into_an_empty_graph() -> None:
    graph = MemoryGraph()
    written = seed(graph, graph, now=NOW)

    assert written["scenarios"] > 0
    assert written["events"] > 0
    assert graph.counts() == (written["entities"], written["edges"])


def test_seeded_events_keep_their_scenario_provenance() -> None:
    """Replayed corpus telemetry must never be presentable as live observation."""
    graph = MemoryGraph()
    seed(graph, graph, now=NOW)

    key = DEMO_EDGES[0][1]
    events = [e for k in graph._events for e in graph._events[k]]
    assert events, "the corpus produced no events"
    assert all(e["provenance"]["source_system"] == "scenario" for e in events)
    assert graph.entity(key) is not None


def test_seed_lands_signals_inside_the_severity_window() -> None:
    """Seeding at the corpus epoch would date every event months back, and the
    map would show a graph of uniformly grey, long-dead entities."""
    graph = MemoryGraph()
    seed(graph, graph, now=NOW)

    # The same `now` the seed used. Reading the wall clock here made this pass
    # for fifteen minutes after NOW and fail for the rest of the day.
    snapshot = graph.snapshot(now=NOW)
    assert any(n["severity"] is not None for n in snapshot["nodes"])


def test_seed_invents_no_dependencies_beyond_the_declared_ones() -> None:
    graph = MemoryGraph()
    seed(graph, graph, now=NOW)

    edges = {(e["source"], e["target"]) for e in graph.snapshot()["edges"]}
    assert edges == set(DEMO_EDGES)


def test_seed_invents_no_user_counts() -> None:
    """A blast radius of zero users is visibly wrong to a reader; an invented
    one is not."""
    graph = MemoryGraph()
    seed(graph, graph, now=NOW)

    assert all(n["estimated_users"] == 0 for n in graph.snapshot()["nodes"])
