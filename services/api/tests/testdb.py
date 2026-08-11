"""Persistence tests.

These run only when Postgres is reachable — `docker compose up -d postgres` in
infra/docker. CI provides it as a service. They are skipped, never silently
passed, when it is absent.

The point of these tests is the invariants the *schema* enforces, not the Python
that calls it: an audit trail that can be edited is not an audit trail, and an
execution row without an authorizing verdict must be unwritable.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import psycopg
import pytest
from app.db import PostgresStore, connect, is_available
from app.engines.audit import AuditKind, AuditRecord
from app.migrate import migrate
from pashupatastra import (
    Environment,
    Hypothesis,
    Incident,
    IncidentSeverity,
    IncidentState,
    RiskContext,
    evaluate,
    incident_id,
)
from pashupatastra.registry import get as get_action

DATABASE_URL = "postgresql://pashupatastra:pashupatastra@localhost:5433/pashupatastra"

pytestmark = pytest.mark.skipif(
    not is_available(DATABASE_URL), reason="Postgres not reachable"
)


@pytest.fixture(scope="module", autouse=True)
def schema():
    migrate(DATABASE_URL)


@pytest.fixture
def store():
    return PostgresStore(DATABASE_URL)


def test_migrations_are_idempotent() -> None:
    assert migrate(DATABASE_URL) == [], "re-running migrations must apply nothing"


def test_applied_migration_cannot_be_edited() -> None:
    """An applied migration whose contents later change is an error, not a
    silent divergence between environments."""
    with connect(DATABASE_URL) as conn:
        original = conn.execute(
            "SELECT checksum FROM schema_migration WHERE filename = 'initial.sql'"
        ).fetchone()["checksum"]
        conn.execute(
            "UPDATE schema_migration SET checksum = 'tampered' WHERE filename = 'initial.sql'"
        )
        conn.commit()
    try:
        with pytest.raises(RuntimeError, match="already applied"):
            migrate(DATABASE_URL)
    finally:
        # Restore the recorded checksum. Deleting the ledger row instead would
        # make the next run re-apply the DDL against an existing schema.
        with connect(DATABASE_URL) as conn:
            conn.execute(
                "UPDATE schema_migration SET checksum = %s WHERE filename = 'initial.sql'",
                (original,),
            )
            conn.commit()


def test_audit_records_round_trip(store: PostgresStore) -> None:
    ref = f"INC-TEST-{datetime.now().timestamp()}"
    store.append_audit(
        AuditRecord(
            kind=AuditKind.POLICY_EVALUATION,
            actor="dharma",
            incident_ref=ref,
            summary="restart_service: risk 10 → autonomous",
            detail={"tier": "autonomous"},
        )
    )
    records = store.audit_records(incident_ref=ref)
    assert len(records) == 1
    assert records[0].detail["tier"] == "autonomous"


def test_audit_trail_is_append_only(store: PostgresStore) -> None:
    """The schema rejects rewriting history, not just the application code."""
    store.append_audit(
        AuditRecord(kind=AuditKind.APPROVAL, actor="human:preet", summary="approved")
    )
    with connect(DATABASE_URL) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("UPDATE audit_record SET summary = 'never happened'")
        conn.rollback()
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("DELETE FROM audit_record")
        conn.rollback()


def test_execution_without_a_verdict_is_unwritable() -> None:
    """`execution.verdict_id` is NOT NULL — the last line of defence beneath
    `require_verdict`, in case anything ever reaches SQL directly."""
    with connect(DATABASE_URL) as conn:
        with pytest.raises(psycopg.errors.NotNullViolation):
            conn.execute(
                """
                INSERT INTO execution (action_id, actor, dry_run, started_at)
                VALUES ('restart_service', 'agent:rogue', false, now())
                """
            )
        conn.rollback()


def test_verdict_and_execution_persist(store: PostgresStore) -> None:
    verdict = evaluate(
        get_action("restart_service"), RiskContext(environment=Environment.DEV)
    )
    verdict_id = store.record_verdict(verdict)
    started = datetime.now().astimezone()
    execution_id = store.record_execution(
        action_id="restart_service",
        verdict_id=verdict_id,
        actor="agent:incident",
        dry_run=True,
        started_at=started,
        finished_at=started + timedelta(seconds=2),
        succeeded=True,
        output="[dry-run]",
    )
    assert execution_id > 0


def test_denied_verdicts_are_stored(store: PostgresStore) -> None:
    """Denials document where autonomy stopped — the research needs them."""
    verdict = evaluate(
        get_action("delete_infrastructure"), RiskContext(environment=Environment.PROD)
    )
    assert verdict.tier.value == "denied"
    store.record_verdict(verdict)
    with connect(DATABASE_URL) as conn:
        n = conn.execute(
            "SELECT count(*) AS n FROM verdict WHERE tier = 'denied'"
        ).fetchone()["n"]
    assert n >= 1


def test_effective_risk_cannot_be_below_base() -> None:
    """Adjustments only ever raise risk — enforced by CHECK, not only in Python."""
    with connect(DATABASE_URL) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                INSERT INTO verdict (action_id, base_risk, effective_risk, tier)
                VALUES ('rollback_deployment', 45, 20, 'autonomous')
                """
            )
        conn.rollback()


def test_hypothesis_requires_evidence() -> None:
    with connect(DATABASE_URL) as conn:
        conn.execute(
            """
            INSERT INTO incident (id, state, severity, opened_at)
            VALUES ('INC-TEST-EV', 'detected', 'low', now())
            ON CONFLICT (id) DO NOTHING
            """
        )
        conn.commit()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """
                INSERT INTO hypothesis (incident_id, statement, confidence, evidence)
                VALUES ('INC-TEST-EV', 'vibes', 0.9, '{}')
                """
            )
        conn.rollback()


def test_incident_round_trip(store: PostgresStore) -> None:
    incident = Incident(
        id=incident_id(2026, 999),
        severity=IncidentSeverity.CRITICAL,
        opened_at=datetime.now().astimezone(),
        hypotheses=[
            Hypothesis(
                statement="connection pool saturated by v4.21",
                confidence=0.91,
                evidence=["evt-deploy-421", "evt-pg-connections"],
            )
        ],
    )
    incident.transition_to(IncidentState.CORRELATED, "agent:incident", "3 adjacent events")
    store.save_incident(incident)

    restored = store.get_incident(incident.id)
    assert restored is not None
    assert restored.state is IncidentState.CORRELATED
    assert restored.top_hypothesis is not None
    assert restored.top_hypothesis.evidence == ["evt-deploy-421", "evt-pg-connections"]


def test_transitions_append_rather_than_rewrite(store: PostgresStore) -> None:
    incident = Incident(
        id=incident_id(2026, 998),
        severity=IncidentSeverity.HIGH,
        opened_at=datetime.now().astimezone(),
    )
    incident.transition_to(IncidentState.CORRELATED, "agent:incident", "correlated")
    store.save_incident(incident)

    incident.transition_to(IncidentState.DIAGNOSED, "agent:incident", "deployment matched")
    store.save_incident(incident)

    with connect(DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT to_state FROM incident_transition WHERE incident_id = %s ORDER BY id",
            (incident.id,),
        ).fetchall()
    assert [r["to_state"] for r in rows] == ["correlated", "diagnosed"]
