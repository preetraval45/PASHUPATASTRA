"""Postgres persistence.

Replaces the in-memory store behind the same seam. Two invariants are enforced
by the schema rather than by this code, deliberately: audit records and incident
transitions reject UPDATE/DELETE via triggers, and `execution.verdict_id` is NOT
NULL so an unauthorized execution cannot be recorded at all.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

import psycopg
from pashupatastra import (
    Hypothesis,
    Incident,
    IncidentSeverity,
    IncidentState,
    Verdict,
)
from psycopg.rows import dict_row

from .config import get_settings
from .engines.audit import AuditKind, AuditRecord


CONNECT_TIMEOUT_SECONDS = 3
"""Short by design. An unreachable database must fail fast so the audit log can
fall back and report `degraded`, rather than stalling every request behind a TCP
timeout."""


@contextmanager
def connect(database_url: str | None = None) -> Iterator[psycopg.Connection]:
    url = database_url or get_settings().database_url
    with psycopg.connect(
        url, row_factory=dict_row, connect_timeout=CONNECT_TIMEOUT_SECONDS
    ) as conn:
        yield conn


def is_available(database_url: str | None = None) -> bool:
    """Whether Postgres is reachable. Used to choose the store at startup."""
    try:
        with connect(database_url) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


class PostgresStore:
    """Durable store. Mirrors the in-memory `Store` interface."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or get_settings().database_url

    # --- audit --------------------------------------------------------------

    def append_audit(self, record: AuditRecord) -> AuditRecord:
        with connect(self.database_url) as conn:
            conn.execute(
                """
                INSERT INTO audit_record (at, kind, actor, incident_id, summary, detail)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    record.at,
                    record.kind.value,
                    record.actor,
                    record.incident_ref,
                    record.summary,
                    json.dumps(record.detail, default=str),
                ),
            )
            conn.commit()
        return record

    def audit_records(
        self, incident_ref: str | None = None, limit: int = 100
    ) -> list[AuditRecord]:
        sql = "SELECT at, kind, actor, incident_id, summary, detail FROM audit_record"
        params: list[Any] = []
        if incident_ref is not None:
            sql += " WHERE incident_id = %s"
            params.append(incident_ref)
        sql += " ORDER BY at DESC, id DESC LIMIT %s"
        params.append(limit)

        with connect(self.database_url) as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            AuditRecord(
                at=row["at"],
                kind=AuditKind(row["kind"]),
                actor=row["actor"],
                incident_ref=row["incident_id"],
                summary=row["summary"],
                detail=row["detail"] or {},
            )
            for row in rows
        ]

    # --- events -------------------------------------------------------------

    def save_events(self, events: list) -> int:
        """Persist normalized events. Idempotent on the ULID, so a connector
        re-polling an overlapping window cannot double-count a sample — which
        would look like a spike that never happened."""
        if not events:
            return 0
        rows = [
            (
                e.id,
                e.schema_version,
                e.event_class.value,
                e.source,
                e.source_version,
                e.occurred_at,
                e.observed_at,
                e.entity_ref.key(),
                e.severity.value if e.severity else None,
                json.dumps(e.payload.model_dump(mode="json")),
                json.dumps(e.provenance.model_dump(mode="json")),
                json.dumps(e.labels),
            )
            for e in events
        ]
        with connect(self.database_url) as conn:
            conn.cursor().executemany(
                """
                INSERT INTO event (
                    id, schema_version, event_class, source, source_version,
                    occurred_at, observed_at, entity_key, severity,
                    payload, provenance, labels
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO NOTHING
                """,
                rows,
            )
            conn.commit()
        return len(rows)

    def quarantine(self, events: list) -> int:
        """Events whose entity could not be resolved. Held and visible, because
        they signal stale topology rather than nothing at all."""
        if not events:
            return 0
        with connect(self.database_url) as conn:
            conn.cursor().executemany(
                "INSERT INTO quarantined_event (raw, source, reason, observed_at)"
                " VALUES (%s, %s, %s, %s)",
                [
                    (json.dumps(q.raw, default=str), q.source, q.reason, q.observed_at)
                    for q in events
                ],
            )
            conn.commit()
        return len(events)

    def entity_events(self, entity_key: str, limit: int = 50) -> list[dict]:
        """Recent events for one entity, newest first.

        Returns raw rows rather than `Event` objects: this feeds a detail view,
        and rehydrating full models only to flatten them again buys nothing.
        """
        with connect(self.database_url) as conn:
            rows = conn.execute(
                """
                SELECT id, event_class, source, occurred_at, observed_at,
                       severity, payload, provenance, labels
                FROM event
                WHERE entity_key = %s
                ORDER BY occurred_at DESC, id DESC
                LIMIT %s
                """,
                (entity_key, limit),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "event_class": r["event_class"],
                "source": r["source"],
                "occurred_at": r["occurred_at"].isoformat(),
                "observed_at": r["observed_at"].isoformat(),
                "severity": r["severity"],
                "payload": r["payload"],
                "provenance": r["provenance"],
                "labels": r["labels"],
            }
            for r in rows
        ]

    def entity(self, entity_key: str) -> dict | None:
        with connect(self.database_url) as conn:
            row = conn.execute(
                "SELECT key, kind, name, namespace, cluster, owner, estimated_users,"
                " first_seen_at, last_seen_at FROM topology_node WHERE key = %s",
                (entity_key,),
            ).fetchone()
        if row is None:
            return None
        return {
            "key": row["key"],
            "kind": row["kind"],
            "name": row["name"],
            "namespace": row["namespace"],
            "cluster": row["cluster"],
            "owner": row["owner"],
            "estimated_users": row["estimated_users"],
            "first_seen": row["first_seen_at"].isoformat(),
            "last_seen": row["last_seen_at"].isoformat(),
        }

    def count_events(self) -> int:
        with connect(self.database_url) as conn:
            return int(conn.execute("SELECT count(*) AS n FROM event").fetchone()["n"])

    def count_audit(self) -> int:
        with connect(self.database_url) as conn:
            return int(conn.execute("SELECT count(*) AS n FROM audit_record").fetchone()["n"])

    # --- verdicts -----------------------------------------------------------

    def record_verdict(self, verdict: Verdict) -> int:
        """Persist a verdict and return its id.

        Denials are stored too — they document where autonomy stopped and why,
        which is the most interesting record for the research.
        """
        with connect(self.database_url) as conn:
            row = conn.execute(
                """
                INSERT INTO verdict (
                    action_id, incident_id, base_risk, effective_risk, adjustments,
                    tier, required_approvers, granted_by, granted_at, expires_at,
                    constraints, denial_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    verdict.action_id,
                    verdict.incident_ref,
                    verdict.base_risk,
                    verdict.effective_risk,
                    json.dumps([a.model_dump() for a in verdict.adjustments]),
                    verdict.tier.value,
                    verdict.required_approvers,
                    verdict.granted_by,
                    verdict.granted_at,
                    verdict.expires_at,
                    json.dumps(verdict.constraints),
                    verdict.denial_reason,
                ),
            ).fetchone()
            conn.commit()
        return int(row["id"])

    # --- executions ---------------------------------------------------------

    def record_execution(
        self,
        action_id: str,
        verdict_id: int,
        actor: str,
        dry_run: bool,
        started_at: datetime,
        finished_at: datetime | None = None,
        succeeded: bool | None = None,
        output: str | None = None,
        incident_ref: str | None = None,
    ) -> int:
        with connect(self.database_url) as conn:
            row = conn.execute(
                """
                INSERT INTO execution (
                    incident_id, action_id, verdict_id, actor, dry_run,
                    started_at, finished_at, succeeded, output
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    incident_ref,
                    action_id,
                    verdict_id,
                    actor,
                    dry_run,
                    started_at,
                    finished_at,
                    succeeded,
                    output,
                ),
            ).fetchone()
            conn.commit()
        return int(row["id"])

    # --- incidents ----------------------------------------------------------

    def save_incident(self, incident: Incident) -> None:
        with connect(self.database_url) as conn:
            conn.execute(
                """
                INSERT INTO incident (
                    id, state, severity, opened_at, closed_at,
                    estimated_users_affected, affected_services,
                    blast_radius_entities, causal_chain, similar_incident_ids
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    state = EXCLUDED.state,
                    closed_at = EXCLUDED.closed_at,
                    estimated_users_affected = EXCLUDED.estimated_users_affected,
                    affected_services = EXCLUDED.affected_services,
                    blast_radius_entities = EXCLUDED.blast_radius_entities,
                    causal_chain = EXCLUDED.causal_chain,
                    similar_incident_ids = EXCLUDED.similar_incident_ids
                """,
                (
                    incident.id,
                    incident.state.value,
                    incident.severity.value,
                    incident.opened_at,
                    incident.closed_at,
                    incident.impact.estimated_users_affected,
                    incident.impact.affected_services,
                    incident.impact.blast_radius_entities,
                    json.dumps([link.model_dump(mode="json") for link in incident.causal_chain]),
                    incident.similar_incident_ids,
                ),
            )

            # Transitions and hypotheses are appended, never rewritten. Existing
            # rows are left alone because the transition table rejects UPDATE.
            existing = conn.execute(
                "SELECT count(*) AS n FROM incident_transition WHERE incident_id = %s",
                (incident.id,),
            ).fetchone()["n"]
            for transition in incident.transitions[existing:]:
                conn.execute(
                    """
                    INSERT INTO incident_transition
                        (incident_id, at, from_state, to_state, actor, justification)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        incident.id,
                        transition.at,
                        transition.from_state.value if transition.from_state else None,
                        transition.to_state.value,
                        transition.actor,
                        transition.justification,
                    ),
                )

            conn.execute("DELETE FROM hypothesis WHERE incident_id = %s", (incident.id,))
            for hypothesis in incident.hypotheses:
                conn.execute(
                    """
                    INSERT INTO hypothesis
                        (incident_id, statement, confidence, evidence,
                         contradicted_by, mechanism)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        incident.id,
                        hypothesis.statement,
                        hypothesis.confidence,
                        hypothesis.evidence,
                        hypothesis.contradicted_by,
                        hypothesis.mechanism,
                    ),
                )
            conn.commit()

    def get_incident(self, incident_id: str) -> Incident | None:
        with connect(self.database_url) as conn:
            row = conn.execute(
                "SELECT * FROM incident WHERE id = %s", (incident_id,)
            ).fetchone()
            if row is None:
                return None
            hypotheses = conn.execute(
                "SELECT * FROM hypothesis WHERE incident_id = %s ORDER BY confidence DESC",
                (incident_id,),
            ).fetchall()

        incident = Incident(
            id=row["id"],
            state=IncidentState(row["state"]),
            severity=IncidentSeverity(row["severity"]),
            opened_at=row["opened_at"],
            closed_at=row["closed_at"],
        )
        incident.impact.estimated_users_affected = row["estimated_users_affected"]
        incident.impact.affected_services = list(row["affected_services"])
        incident.impact.blast_radius_entities = row["blast_radius_entities"]
        incident.similar_incident_ids = list(row["similar_incident_ids"])
        incident.hypotheses = [
            Hypothesis(
                statement=h["statement"],
                confidence=h["confidence"],
                evidence=list(h["evidence"]),
                contradicted_by=list(h["contradicted_by"]),
                mechanism=list(h["mechanism"]),
            )
            for h in hypotheses
        ]
        return incident

    def list_incidents(self) -> list[Incident]:
        with connect(self.database_url) as conn:
            ids = [r["id"] for r in conn.execute("SELECT id FROM incident ORDER BY opened_at DESC")]
        return [i for i in (self.get_incident(i) for i in ids) if i is not None]
