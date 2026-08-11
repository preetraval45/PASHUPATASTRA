"""Retention.

Postgres is the hot store: recent events, live topology, open incidents. It is
not the archive. Left unbounded, the event table grows until the queries that
diagnose incidents are the ones slowed by the data volume — the system gets
worse at its job in proportion to how much it has seen.

The split (docs/DEPLOYMENT.md):

    Postgres      recent events, incidents, verdicts, audit — queried live
    OpenSearch    log search over a longer horizon
    S3            incident artifacts, snapshots, benchmark runs — cold

**The audit trail is never pruned.** It is the record every claim and every
authorization rests on, and an append-only log with a delete path is not
append-only. Its growth is bounded by writing summaries rather than payloads,
not by discarding history. The same applies to incident transitions: an incident
whose timeline has been partially deleted cannot be reviewed, and post-incident
review is the entire point of keeping it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .db import connect
from .engines.audit import AUDIT, AuditKind, AuditRecord

DEFAULT_EVENT_RETENTION = timedelta(days=14)
"""Long enough to diagnose a recurring incident by comparing it with its
predecessor; short enough that the hot store stays fast. Smriti keeps the
*incident*, not every metric sample that produced it."""

DEFAULT_QUARANTINE_RETENTION = timedelta(days=7)

# Tables that may never be pruned, and why — checked at runtime, not trusted to
# reviewers noticing.
PROTECTED = {
    "audit_record": "append-only: the record every claim and authorization rests on",
    "incident_transition": "an incident with a partial timeline cannot be reviewed",
    "incident": "incidents are Smriti's memory; retention belongs to Smriti, not here",
    "verdict": "denials document where autonomy stopped — the research needs them",
    "execution": "what the system actually did must outlive what it observed",
}


class ProtectedTable(Exception):
    """Raised when a prune targets a table that must not lose rows."""


@dataclass
class RetentionResult:
    events_deleted: int = 0
    quarantined_deleted: int = 0
    dry_run: bool = True

    def snapshot(self) -> dict[str, int | bool]:
        return {
            "events_deleted": self.events_deleted,
            "quarantined_deleted": self.quarantined_deleted,
            "dry_run": self.dry_run,
        }


def assert_prunable(table: str) -> None:
    if table in PROTECTED:
        raise ProtectedTable(f"{table} may not be pruned — {PROTECTED[table]}")


def apply_retention(
    events_older_than: timedelta = DEFAULT_EVENT_RETENTION,
    quarantine_older_than: timedelta = DEFAULT_QUARANTINE_RETENTION,
    dry_run: bool = True,
    database_url: str | None = None,
) -> RetentionResult:
    """Prune the hot store.

    Dry-run by default. Deleting telemetry is irreversible and quiet, and a
    retention job that runs before anyone has looked at what it would remove is
    how six months of evidence disappears in a config typo.
    """
    for table in ("event", "quarantined_event"):
        assert_prunable(table)

    result = RetentionResult(dry_run=dry_run)
    with connect(database_url) as conn:
        events = conn.execute(
            "SELECT count(*) AS n FROM event WHERE observed_at < now() - %s::interval",
            (f"{int(events_older_than.total_seconds())} seconds",),
        ).fetchone()["n"]
        quarantined = conn.execute(
            "SELECT count(*) AS n FROM quarantined_event"
            " WHERE observed_at < now() - %s::interval",
            (f"{int(quarantine_older_than.total_seconds())} seconds",),
        ).fetchone()["n"]

        result.events_deleted = int(events)
        result.quarantined_deleted = int(quarantined)

        if not dry_run:
            conn.execute(
                "DELETE FROM event WHERE observed_at < now() - %s::interval",
                (f"{int(events_older_than.total_seconds())} seconds",),
            )
            conn.execute(
                "DELETE FROM quarantined_event WHERE observed_at < now() - %s::interval",
                (f"{int(quarantine_older_than.total_seconds())} seconds",),
            )
            conn.commit()

    # Recorded either way. A retention run that leaves no trace makes "the data
    # was never collected" and "the data was aged out" indistinguishable.
    AUDIT.append(
        AuditRecord(
            kind=AuditKind.OBSERVATION,
            actor="retention",
            summary=(
                f"retention {'preview' if dry_run else 'applied'}: "
                f"{result.events_deleted} events, "
                f"{result.quarantined_deleted} quarantined"
            ),
            detail=result.snapshot(),
        )
    )
    return result
