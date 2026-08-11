"""Perception orchestration: poll → persist → reconcile the graph."""

from __future__ import annotations

from datetime import datetime

import pytest
from app.db import PostgresStore, connect, is_available
from app.engines.drishti import Drishti
from app.graph import GraphStore
from app.migrate import migrate
from drishti import Connector, Harvest, Window
from pashupatastra import (
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Provenance,
    QuarantinedEvent,
)
from pashupatastra.events import MetricPayload, TracePayload

DATABASE_URL = "postgresql://pashupatastra:pashupatastra@localhost:5433/pashupatastra"

pytestmark = pytest.mark.skipif(not is_available(DATABASE_URL), reason="Postgres not reachable")


def _event(name: str, payload, event_class: EventClass) -> Event:
    now = datetime.now().astimezone()
    return Event(
        event_class=event_class,
        source="fake",
        occurred_at=now,
        observed_at=now,
        entity_ref=EntityRef(kind=EntityKind.SERVICE, id=name, name=name),
        payload=payload,
        provenance=Provenance(source_system="fake", query="up"),
    )


class FakeConnector(Connector):
    name = "fake"

    def __init__(self, harvest: Harvest) -> None:
        self._harvest = harvest

    def poll(self, window: Window) -> Harvest:
        return self._harvest


class BrokenConnector(Connector):
    name = "broken"

    def poll(self, window: Window) -> Harvest:
        raise ConnectionError("upstream unreachable")


@pytest.fixture(scope="module", autouse=True)
def schema():
    migrate(DATABASE_URL)


@pytest.fixture
def drishti_for():
    def build(harvest: Harvest, extra: list | None = None) -> Drishti:
        return Drishti(
            connectors=[FakeConnector(harvest), *(extra or [])],
            store=PostgresStore(DATABASE_URL),
            graph=GraphStore(DATABASE_URL),
        )

    return build


def test_poll_persists_events_and_builds_topology(drishti_for) -> None:
    harvest = Harvest(
        events=[
            _event("ingest-api", MetricPayload(name="cpu", value=42.0), EventClass.METRIC),
            _event(
                "ingest-frontend",
                TracePayload(
                    trace_id="t",
                    span_id="s",
                    duration_ms=10.0,
                    status="ok",
                    service_hops=["ingest-frontend", "ingest-api"],
                ),
                EventClass.TRACE,
            ),
        ]
    )
    result = drishti_for(harvest).poll(Window.trailing(300))

    assert result.healthy
    assert result.events_stored == 2
    assert result.nodes_upserted >= 2

    graph = GraphStore(DATABASE_URL)
    radius = graph.blast_radius("service:ingest-api")
    assert "service:ingest-frontend" in radius.affected


def test_events_are_idempotent_across_overlapping_polls(drishti_for) -> None:
    """A re-poll of an overlapping window must not double-count a sample —
    duplicates would look like a spike that never happened."""
    harvest = Harvest(
        events=[_event("dedupe-api", MetricPayload(name="cpu", value=1.0), EventClass.METRIC)]
    )
    store = PostgresStore(DATABASE_URL)
    before = store.count_events()

    drishti = drishti_for(harvest)
    drishti.poll(Window.trailing(60))
    drishti.poll(Window.trailing(60))

    assert store.count_events() == before + 1


def test_quarantined_events_are_stored_not_dropped(drishti_for) -> None:
    harvest = Harvest(
        quarantined=[
            QuarantinedEvent(
                raw={"metric": {"foo": "bar"}},
                source="fake",
                reason="no recognizable entity label",
                observed_at=datetime.now().astimezone(),
            )
        ]
    )
    result = drishti_for(harvest).poll(Window.trailing(60))
    assert result.quarantined == 1

    with connect(DATABASE_URL) as conn:
        n = conn.execute("SELECT count(*) AS n FROM quarantined_event").fetchone()["n"]
    assert n >= 1


def test_one_failing_connector_does_not_stop_the_others(drishti_for) -> None:
    """Partial perception is degraded, not useless — but the failure is recorded
    so nothing downstream mistakes a blind spot for an all-clear."""
    harvest = Harvest(
        events=[_event("resilient-api", MetricPayload(name="cpu", value=5.0), EventClass.METRIC)]
    )
    result = drishti_for(harvest, extra=[BrokenConnector()]).poll(Window.trailing(60))

    assert result.events_stored == 1, "the healthy connector still delivered"
    assert not result.healthy
    assert any("broken" in e for e in result.errors)


def test_poll_is_audited(drishti_for) -> None:
    from app.engines.audit import AUDIT

    drishti_for(Harvest()).poll(Window.trailing(60))
    kinds = [r.kind.value for r in AUDIT.records(limit=20)]
    assert "observation" in kinds
