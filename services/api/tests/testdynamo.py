"""The DynamoDB store, and the backend decision in front of it.

Split deliberately. The conversions and the resolver are pure logic and run
everywhere; the round-trips need a real table and skip without one, because a
mock of DynamoDB would be asserting that my idea of DynamoDB matches my code —
which is the one thing a test like that cannot tell you.

Set `PASHU_DYNAMO_TABLE` to run the integration half. `scripts/createdynamo.py`
makes the table. The round-trips write into a `test` namespace, never `prod` —
they did once, and a fixture host turned up on the live service map.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from app.dynamo import _numbers_to_decimal, _plain

TABLE = os.environ.get("PASHU_DYNAMO_TABLE")
needs_table = pytest.mark.skipif(not TABLE, reason="PASHU_DYNAMO_TABLE is not set")

NOW = datetime(2026, 8, 21, 12, 0, 0).astimezone()


# --- the number boundary ------------------------------------------------------


def test_decimals_become_python_numbers() -> None:
    """DynamoDB has no float type. A `Decimal` that reaches Pydantic validates
    fine and then serialises to JSON as a *string*, so the dashboard renders
    "0.94" as text where it expected a number."""
    assert _plain(Decimal("0.94")) == 0.94
    assert isinstance(_plain(Decimal("0.94")), float)


def test_whole_decimals_become_integers() -> None:
    """`Decimal("3")` to `3.0` would render an entity count as "3.0"."""
    assert _plain(Decimal("3")) == 3
    assert isinstance(_plain(Decimal("3")), int)


def test_conversion_reaches_inside_structures() -> None:
    """Payloads and provenance are nested, and a confidence buried two levels
    down is exactly the one that would slip through."""
    nested = {"a": [Decimal("1.5"), {"b": Decimal("2")}], "c": "text"}
    assert _plain(nested) == {"a": [1.5, {"b": 2}], "c": "text"}


def test_floats_are_converted_on_the_way_in() -> None:
    """DynamoDB rejects a float outright, so this is not cosmetic."""
    assert _numbers_to_decimal({"x": [0.5]}) == {"x": [Decimal("0.5")]}


def test_the_round_trip_preserves_a_confidence() -> None:
    assert _plain(_numbers_to_decimal({"confidence": 0.97}))["confidence"] == 0.97


# --- the backend decision -----------------------------------------------------


def test_no_configuration_means_no_durable_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """With neither a table nor a database, every store falls back to memory and
    health says `degraded` — which is true, and is the point of saying it."""
    from app import backend
    from app.config import get_settings

    monkeypatch.setenv("PASHU_DYNAMO_TABLE", "")
    monkeypatch.setenv("PASHU_DATABASE_URL", "")
    get_settings.cache_clear()
    backend.reset()
    try:
        assert backend.durable() is None
    finally:
        get_settings.cache_clear()
        backend.reset()


def test_every_seam_gets_the_same_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Incidents, the audit trail and the topology graph each used to decide
    this for themselves. They could disagree — an audit trail on a database
    while incidents sat in memory would report `degraded` from one seam and
    `ok` from another, and `/health` would be answering for a third of the
    system."""
    from app import backend
    from app.config import get_settings
    from app.graph import _durable as graph_durable
    from app.engines.audit import AUDIT
    from app.store import STORE

    monkeypatch.setenv("PASHU_DYNAMO_TABLE", "")
    monkeypatch.setenv("PASHU_DATABASE_URL", "")
    get_settings.cache_clear()
    backend.reset()
    try:
        assert STORE.durable is AUDIT.durable is graph_durable() is False
    finally:
        get_settings.cache_clear()
        backend.reset()


def test_postgres_does_not_answer_graph_questions() -> None:
    """`GraphStore` holds the topology SQL, so Postgres is routed through it.
    DynamoDB and the memory mirror answer for themselves and say so. Getting
    this wrong sent DynamoDB into `connect()` to open a Postgres connection."""
    from app.db import PostgresStore
    from app.dynamo import DynamoStore
    from app.graphmemory import MemoryGraph

    assert getattr(PostgresStore, "answers_graph", False) is False
    assert DynamoStore.answers_graph is True
    assert MemoryGraph.answers_graph is True


def test_the_default_namespace_is_not_shared_with_tests() -> None:
    """The guard that keeps a test fixture off the live service map. `prod` and
    `test` must name different slices of the table; if this ever collapses to
    one value the round-trips below start writing to the deployed console."""
    from app.dynamo import DynamoStore

    assert DynamoStore(namespace=NAMESPACE)._pk("NODE") != DynamoStore(namespace="prod")._pk("NODE")


def test_a_namespace_is_always_applied() -> None:
    """A bare `"NODE"` reaching the table would sit in whatever namespace last
    used that literal — which is how the two environments got mixed."""
    from app.dynamo import DynamoStore

    store = DynamoStore(namespace=NAMESPACE)
    assert store._pk("NODE").endswith("#NODE")
    assert store._pk("NODE").startswith(NAMESPACE)


def test_each_backend_names_itself() -> None:
    """`/health` reports the store by name. It was hardcoded to "postgres",
    which meant a DynamoDB deployment described the wrong one — and the whole
    value of that field is that a reader can trust it."""
    from app.db import PostgresStore
    from app.dynamo import DynamoStore

    assert DynamoStore.name == "dynamodb"
    assert PostgresStore.name == "postgres"


# --- round-trips against a real table -----------------------------------------


NAMESPACE = "test"


@pytest.fixture
def store():
    from app.dynamo import DynamoStore

    instance = DynamoStore(namespace=NAMESPACE)
    if not instance.available():
        pytest.skip(f"table {instance.table_name} is not reachable")
    return instance


@needs_table
def test_an_incident_round_trips(store) -> None:
    from app.demoincidents import scenarios

    original = scenarios(NOW)[0].incident
    store.save_incident(original)
    restored = store.get_incident(original.id)

    assert restored is not None
    assert restored.id == original.id
    # The confidence is the value the Decimal boundary would corrupt.
    assert restored.hypotheses[0].confidence == original.hypotheses[0].confidence
    assert len(restored.causal_chain) == len(original.causal_chain)
    assert restored.causal_chain[0].attack_technique == original.causal_chain[0].attack_technique


@needs_table
def test_audit_records_come_back_newest_first(store) -> None:
    from app.engines.audit import AuditKind, AuditRecord

    marker = f"ordering-{NOW.timestamp()}"
    for index in range(3):
        store.append_audit(
            AuditRecord(
                at=NOW + timedelta(seconds=index),
                kind=AuditKind.OBSERVATION,
                actor="test",
                incident_ref=marker,
                summary=f"record {index}",
            )
        )

    records = store.audit_records(incident_ref=marker, limit=10)
    assert [r.summary for r in records] == ["record 2", "record 1", "record 0"]


@needs_table
def test_two_records_in_the_same_instant_both_survive(store) -> None:
    """Without a sequence in the sort key the second overwrites the first, and
    an audit trail that drops a record under load is not an audit trail."""
    from app.engines.audit import AuditKind, AuditRecord

    marker = f"collision-{NOW.timestamp()}"
    for index in range(2):
        store.append_audit(
            AuditRecord(
                at=NOW,  # identical timestamps
                kind=AuditKind.OBSERVATION,
                actor="test",
                incident_ref=marker,
                summary=f"same instant {index}",
            )
        )

    assert len(store.audit_records(incident_ref=marker, limit=10)) == 2


@needs_table
def test_blast_radius_matches_the_reference_implementation(store) -> None:
    """The traversal is `TopologyGraph`'s, hydrated from the table. A fourth
    implementation of blast radius would be a fourth answer to a question risk
    scoring depends on."""
    from pashupatastra import Edge, EntityKind, EntityRef, Node
    from pashupatastra.topology import TopologyGraph

    refs = {
        key: EntityRef(kind=EntityKind(key.split(":")[0]), id=key.split(":")[1], name=key.split(":")[1])
        for key in ("host:rt-a", "asset:rt-b", "account:rt-c")
    }
    nodes = [Node(ref=ref, estimated_users=0) for ref in refs.values()]
    edges = [
        Edge(source="host:rt-a", target="account:rt-c"),
        Edge(source="asset:rt-b", target="host:rt-a"),
    ]
    store.upsert_nodes(nodes)
    store.upsert_edges(edges)

    reference = TopologyGraph()
    for node in nodes:
        reference.add_node(node)
    for edge in edges:
        reference.add_edge(edge)

    assert store.blast_radius("account:rt-c") == reference.blast_radius("account:rt-c")


@needs_table
def test_an_event_is_findable_by_id_and_by_entity(store) -> None:
    """Both are needed: a citation resolves by id, an entity page lists by
    entity, and only one of them is answerable from the table's own keys."""
    from app.demoincidents import scenarios

    scenario = scenarios(NOW)[0]
    store.save_events(scenario.events(NOW))

    signal = scenario.signals[0]
    assert store.event(signal.id) is not None
    assert store.event("SEC-9999-nope") is None

    by_entity = store.entity_events(signal.entity.key(), limit=20)
    assert any(row["id"] == signal.id for row in by_entity)


@needs_table
def test_an_upsert_without_a_user_count_does_not_erase_one(store) -> None:
    """The rule the Postgres upsert enforces with its CASE expression, and the
    memory mirror repeats. A connector that cannot see user counts must not zero
    out what another connector established — blast radius reads this number."""
    from pashupatastra import EntityKind, EntityRef, Node

    ref = EntityRef(kind=EntityKind.ASSET, id="rt-users", name="rt-users")
    store.upsert_nodes([Node(ref=ref, estimated_users=250)])
    store.upsert_nodes([Node(ref=ref, estimated_users=0)])

    assert store.entity(ref.key())["estimated_users"] == 250


@needs_table
def test_no_read_path_leaks_the_tables_own_keys(store) -> None:
    """`PK`, `SK` and `GSI1PK` are storage, not API.

    `recent_events` published all three, and `GSI1PK` carries the namespace —
    so a public route was handing out `prod#ENTITY#…` along with three fields
    the caller had to JSON-parse itself. The cause was skipping `_event_row`
    and returning the row as stored; asserted over every read that returns
    events, so the next one added cannot repeat it.
    """
    from app.demoincidents import scenarios

    scenario = scenarios(NOW)[0]
    store.save_events(scenario.events(NOW))
    signal = scenario.signals[0]

    reads = [
        [store.event(signal.id)],
        store.entity_events(signal.entity.key(), limit=5),
        store.recent_events(limit=5),
    ]
    for rows in reads:
        for row in rows:
            assert row is not None
            assert not {"PK", "SK", "GSI1PK", "GSI1SK"} & set(row)
            # And the three structured fields come back structured.
            assert isinstance(row["payload"], dict)
            assert isinstance(row["provenance"], dict)
            assert isinstance(row["labels"], dict)
