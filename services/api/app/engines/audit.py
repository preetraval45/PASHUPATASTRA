"""Audit engine — append-only.

Records are written *before* execution, never after (docs/SECURITY.md T6). Policy
evaluations are recorded whether or not they resulted in execution; denials are
the most interesting records for the research.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AuditKind(StrEnum):
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    POLICY_EVALUATION = "policy_evaluation"
    APPROVAL = "approval"
    EXECUTION_ATTEMPT = "execution_attempt"
    EXECUTION_RESULT = "execution_result"
    VERIFICATION = "verification"
    ESCALATION = "escalation"
    AGENT_TURN = "agent_turn"
    """One question answered by the agent.

    Its own kind rather than an observation. An observation is something the
    platform saw; this is something it *said*, and the two answer different
    questions when a reader is working out where a claim came from. Filing them
    together also made the agent's turns invisible in a trail full of telemetry.
    """


class AuditRecord(BaseModel):
    at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    kind: AuditKind
    actor: str
    incident_ref: str | None = None
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditLog:
    """Writes to Postgres when it is reachable, otherwise to memory.

    The fallback exists so local development and CI without a database still
    work. It is *not* acceptable in production: an audit trail that disappears
    on restart is not an audit trail, so `degraded` is surfaced on the health
    endpoint rather than failing quietly.

    On AWS, CloudTrail is the independent mirror of this record
    (docs/DEPLOYMENT.md).
    """

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self._backend: object | None = None
        self._resolved = False

    def _store(self):
        from ..backend import durable

        return durable()

    @property
    def durable(self) -> bool:
        return self._store() is not None

    def append(self, record: AuditRecord) -> AuditRecord:
        store = self._store()
        if store is not None:
            store.append_audit(record)
        else:
            self._records.append(record)
        return record

    def records(self, incident_ref: str | None = None, limit: int = 100) -> list[AuditRecord]:
        store = self._store()
        if store is not None:
            return store.audit_records(incident_ref=incident_ref, limit=limit)
        rows = self._records
        if incident_ref is not None:
            rows = [r for r in rows if r.incident_ref == incident_ref]
        return list(reversed(rows[-limit:]))

    def __len__(self) -> int:
        store = self._store()
        if store is not None:
            return store.count_audit()
        return len(self._records)


AUDIT = AuditLog()
