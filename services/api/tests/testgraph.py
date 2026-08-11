"""Topology graph in Postgres.

The point of this file is parity. `TopologyGraph` in packages/core is the
reference implementation of blast radius; the recursive CTE is the Postgres
default proposed by the Graph ADR. If they ever disagree, blast radius becomes
environment-dependent — and blast radius is an input to risk scoring, so a
disagreement would mean the same action carries different authority depending on
which code path answered.

Every structural case is asserted against both.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from app.db import connect, is_available
from app.graph import GraphStore
from app.migrate import migrate
from pashupatastra import EntityKind, EntityRef, Node, TopologyGraph
from pashupatastra.topology import Edge

DATABASE_URL = "postgresql://pashupatastra:pashupatastra@localhost:5433/pashupatastra"

pytestmark = pytest.mark.skipif(not is_available(DATABASE_URL), reason="Postgres not reachable")


def ref(kind: EntityKind, name: str) -> EntityRef:
    return EntityRef(kind=kind, id=name, name=name)


# (kind, name, estimated_users)
NODES = [
    (EntityKind.DATABASE, "postgres", 0),
    (EntityKind.CACHE, "redis", 0),
    (EntityKind.SERVICE, "api", 0),
    (EntityKind.SERVICE, "frontend", 1200),
    (EntityKind.SERVICE, "worker", 0),
    (EntityKind.SERVICE, "billing", 300),
    (EntityKind.SERVICE, "search", 50),
]

# source depends on target: a failure in target propagates to source.
EDGES = [
    ("service:api", "database:postgres"),
    ("service:api", "cache:redis"),
    ("service:frontend", "service:api"),
    ("service:worker", "database:postgres"),
    ("service:billing", "service:api"),
    # `search` is deliberately unconnected — it is the negative case.
]


@pytest.fixture(scope="module", autouse=True)
def seeded():
    migrate(DATABASE_URL)
    with connect(DATABASE_URL) as conn:
        conn.execute("DELETE FROM topology_edge")
        conn.execute("DELETE FROM topology_node")
        conn.commit()

    store = GraphStore(DATABASE_URL)
    store.upsert_nodes([Node(ref=ref(k, n), estimated_users=u) for k, n, u in NODES])
    store.upsert_edges([Edge(source=s, target=t) for s, t in EDGES])
    return store


@pytest.fixture(scope="module")
def reference() -> TopologyGraph:
    graph = TopologyGraph()
    for kind, name, users in NODES:
        graph.add_node(Node(ref=ref(kind, name), estimated_users=users))
    for source, target in EDGES:
        graph.add_edge(Edge(source=source, target=target))
    return graph


@pytest.fixture
def store() -> GraphStore:
    return GraphStore(DATABASE_URL)


@pytest.mark.parametrize(
    "origin",
    [
        "database:postgres",
        "cache:redis",
        "service:api",
        "service:frontend",
        "service:search",
        "service:nonexistent",
    ],
)
def test_blast_radius_matches_the_reference_implementation(
    store: GraphStore, reference: TopologyGraph, origin: str
) -> None:
    from_db = store.blast_radius(origin)
    from_core = reference.blast_radius(origin)
    assert sorted(from_db.affected) == sorted(from_core.affected), origin
    assert from_db.estimated_users == from_core.estimated_users, origin


def test_blast_radius_propagates_transitively(store: GraphStore) -> None:
    """postgres → api → {frontend, billing}. Two hops, not one."""
    radius = store.blast_radius("database:postgres")
    assert set(radius.affected) == {
        "service:api",
        "service:frontend",
        "service:worker",
        "service:billing",
    }
    assert radius.estimated_users == 1500  # frontend 1200 + billing 300


def test_origin_is_not_in_its_own_blast_radius(store: GraphStore) -> None:
    assert "database:postgres" not in store.blast_radius("database:postgres").affected


def test_direction_matters(store: GraphStore) -> None:
    """The frontend depends on the API, not the reverse. A failed frontend must
    not report the database as affected."""
    assert store.blast_radius("service:frontend").affected == []


def test_unknown_origin_returns_empty_rather_than_failing(store: GraphStore) -> None:
    radius = store.blast_radius("service:nonexistent")
    assert radius.affected == []
    assert radius.estimated_users == 0


def test_depth_limit_is_honoured(store: GraphStore) -> None:
    shallow = store.blast_radius("database:postgres", max_depth=1)
    assert set(shallow.affected) == {"service:api", "service:worker"}
    assert "service:frontend" not in shallow.affected


def test_cycles_terminate(store: GraphStore) -> None:
    """A dependency cycle must not loop forever or re-add the origin."""
    store.upsert_nodes(
        [Node(ref=ref(EntityKind.SERVICE, "a")), Node(ref=ref(EntityKind.SERVICE, "b"))]
    )
    store.upsert_edges(
        [Edge(source="service:a", target="service:b"), Edge(source="service:b", target="service:a")]
    )
    radius = store.blast_radius("service:a")
    assert radius.affected == ["service:b"]


def test_unconnected_entities_are_not_adjacent(store: GraphStore) -> None:
    """The correlation gate: two failures in the same minute are two incidents
    unless the graph connects them."""
    assert not store.adjacent("service:search", "service:billing")
    assert store.adjacent("service:billing", "database:postgres")


def test_reconciliation_is_idempotent(store: GraphStore) -> None:
    before = store.counts()
    store.upsert_nodes([Node(ref=ref(EntityKind.SERVICE, "api"))])
    store.upsert_edges([Edge(source="service:api", target="database:postgres")])
    assert store.counts() == before


def test_a_connector_without_user_counts_does_not_zero_them(store: GraphStore) -> None:
    """A later poll that cannot see user counts must not erase what another
    connector established — that would silently shrink blast radius."""
    store.upsert_nodes([Node(ref=ref(EntityKind.SERVICE, "frontend"), estimated_users=0)])
    assert store.blast_radius("service:api").estimated_users == 1500


def test_stale_nodes_are_surfaced_not_deleted(store: GraphStore) -> None:
    assert store.stale_nodes(timedelta(days=365)) == []
    stale = {n["key"] for n in store.stale_nodes(timedelta(seconds=-1))}
    assert "service:api" in stale
    assert store.counts()[0] > 0, "listing stale nodes must not delete them"


def test_pruning_is_dry_run_by_default(store: GraphStore) -> None:
    """Expiring stale nodes on a timer is the wrong instinct: deleting a node
    whose connector merely broke shrinks blast radius, which lowers effective
    risk, which would hand actions more autonomy precisely because the system
    had gone blind."""
    before = store.counts()
    result = store.prune_stale(timedelta(seconds=-1))

    assert result["dry_run"] is True
    assert result["removed"] == 0
    assert result["candidates"], "it still says what it would remove"
    assert store.counts() == before


def test_pruning_removes_only_when_explicitly_asked(store: GraphStore) -> None:
    store.upsert_nodes([Node(ref=ref(EntityKind.SERVICE, "doomed"))])
    store.upsert_edges([Edge(source="service:doomed", target="database:postgres")])
    before_nodes, before_edges = store.counts()

    result = store.prune_stale(timedelta(seconds=-1), dry_run=False)

    assert result["dry_run"] is False
    assert result["removed"] == before_nodes
    assert result["edges_removed"] == before_edges
    assert store.counts() == (0, 0)
