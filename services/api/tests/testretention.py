"""Retention.

The interesting assertions are about what may *not* be deleted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from app.db import connect, is_available
from app.migrate import migrate
from app.retention import (
    PROTECTED,
    ProtectedTable,
    apply_retention,
    assert_prunable,
)

DATABASE_URL = "postgresql://pashupatastra:pashupatastra@localhost:5433/pashupatastra"

pytestmark = pytest.mark.skipif(not is_available(DATABASE_URL), reason="Postgres not reachable")


@pytest.fixture(scope="module", autouse=True)
def schema():
    migrate(DATABASE_URL)


def seed_event(observed_at: datetime, event_id: str) -> None:
    with connect(DATABASE_URL) as conn:
        conn.execute(
            """
            INSERT INTO event (id, schema_version, event_class, source, occurred_at,
                               observed_at, entity_key, payload, provenance)
            VALUES (%s, 'v0', 'metric', 'test', %s, %s, 'service:retention-test',
                    '{"kind":"metric","name":"cpu","value":1.0}',
                    '{"source_system":"test"}')
            ON CONFLICT (id) DO NOTHING
            """,
            (event_id, observed_at, observed_at),
        )
        conn.commit()


def count_events() -> int:
    with connect(DATABASE_URL) as conn:
        return int(
            conn.execute(
                "SELECT count(*) AS n FROM event WHERE entity_key = 'service:retention-test'"
            ).fetchone()["n"]
        )


@pytest.mark.parametrize("table", sorted(PROTECTED))
def test_protected_tables_refuse_pruning(table: str) -> None:
    """An append-only log with a delete path is not append-only."""
    with pytest.raises(ProtectedTable):
        assert_prunable(table)


def test_the_audit_trail_is_protected() -> None:
    assert "audit_record" in PROTECTED
    assert "incident_transition" in PROTECTED, "a partial timeline cannot be reviewed"
    assert "verdict" in PROTECTED, "denials document where autonomy stopped"


def test_prunable_tables_pass() -> None:
    assert_prunable("event")
    assert_prunable("quarantined_event")


def test_dry_run_reports_without_deleting() -> None:
    """Deleting telemetry is irreversible and quiet. A retention job that runs
    before anyone has seen what it would remove is how evidence disappears in a
    config typo."""
    old = datetime.now(timezone.utc) - timedelta(days=40)
    seed_event(old, "01RETENTIONDRYRUN000000000")
    before = count_events()

    result = apply_retention(
        events_older_than=timedelta(days=30), dry_run=True, database_url=DATABASE_URL
    )

    assert result.dry_run is True
    assert result.events_deleted >= 1
    assert count_events() == before, "nothing removed in a preview"


def test_applying_retention_deletes_only_what_is_old() -> None:
    old = datetime.now(timezone.utc) - timedelta(days=40)
    fresh = datetime.now(timezone.utc)
    seed_event(old, "01RETENTIONOLD0000000000AA")
    seed_event(fresh, "01RETENTIONFRESH000000000B")

    apply_retention(
        events_older_than=timedelta(days=30), dry_run=False, database_url=DATABASE_URL
    )

    with connect(DATABASE_URL) as conn:
        remaining = {
            r["id"]
            for r in conn.execute(
                "SELECT id FROM event WHERE entity_key = 'service:retention-test'"
            ).fetchall()
        }
    assert "01RETENTIONFRESH000000000B" in remaining
    assert "01RETENTIONOLD0000000000AA" not in remaining


def test_retention_runs_are_audited() -> None:
    """'Never collected' and 'aged out' must not be indistinguishable."""
    from app.engines.audit import AUDIT

    apply_retention(dry_run=True, database_url=DATABASE_URL)
    summaries = [r.summary for r in AUDIT.records(limit=20)]
    assert any("retention" in s for s in summaries)


def test_audit_rows_survive_a_retention_run() -> None:
    from app.engines.audit import AUDIT

    before = len(AUDIT)
    apply_retention(
        events_older_than=timedelta(seconds=0), dry_run=False, database_url=DATABASE_URL
    )
    assert len(AUDIT) >= before, "retention must never shrink the audit trail"
