"""Audit engine — append-only.

Records are written *before* execution, never after (docs/SECURITY.md T6). Policy
evaluations are recorded whether or not they resulted in execution; denials are
the most interesting records for the research.
"""

from __future__ import annotations

import re
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


_SCENARIO = re.compile(r"^INC-\d{4}-\d{4}$")
SCENARIO_RECORDS = 200
"""More than the seeded scenarios write, so hiding theirs never shortens a page of real ones."""


def _hide_scenarios() -> bool:
    """A deployment that lists live incidents keeps the written scenarios for drills only, and
    their seeded trail out of every view of what the system has done."""
    from ..config import get_settings

    return get_settings().live_incidents


def _real(rows: list[AuditRecord]) -> list[AuditRecord]:
    return [r for r in rows if not (r.incident_ref and _SCENARIO.match(r.incident_ref))]


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

    def records(
        self, incident_ref: str | None = None, limit: int = 100, kind: AuditKind | None = None
    ) -> list[AuditRecord]:
        """The newest `limit` records matching the filters, newest first.

        Filtered by the store, before the limit, so "no approvals" means none
        were recorded, not that none were among the newest hundred lines.
        """
        if incident_ref is None and _hide_scenarios():
            # Asked for a specific incident's trail (a drill's), the scenario's records are the
            # answer; asked for the system's activity, they are not activity.
            return _real(self._records_raw(None, limit + SCENARIO_RECORDS, kind))[:limit]
        return self._records_raw(incident_ref, limit, kind)

    def _records_raw(
        self, incident_ref: str | None, limit: int, kind: AuditKind | None
    ) -> list[AuditRecord]:
        store = self._store()
        if store is not None:
            return store.audit_records(incident_ref=incident_ref, limit=limit, kind=kind)
        rows = self._records
        if incident_ref is not None:
            rows = [r for r in rows if r.incident_ref == incident_ref]
        if kind is not None:
            rows = [r for r in rows if r.kind == kind]
        return list(reversed(rows[-limit:]))

    def since(self, when: datetime, kind: AuditKind | None = None) -> list[AuditRecord]:
        """Every record at or after `when`, newest first, optionally of one kind.

        For roll-ups — usage per day, attempts to date — which need a window
        rather than the newest N. Filtered on the record's own `at` in every
        backend, so the answer does not depend on how a store happens to order
        its keys.
        """
        store = self._store()
        rows = store.audit_since(when) if store is not None else list(reversed(self._records))
        rows = [r for r in rows if r.at >= when and (kind is None or r.kind is kind)]
        return _real(rows) if _hide_scenarios() else rows

    def __len__(self) -> int:
        store = self._store()
        if store is not None:
            return store.count_audit()
        return len(self._records)


AUDIT = AuditLog()
