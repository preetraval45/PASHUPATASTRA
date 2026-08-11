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


class AuditRecord(BaseModel):
    at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    kind: AuditKind
    actor: str
    incident_ref: str | None = None
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditLog:
    """In-memory for now; Phase 0.5 moves this to Postgres with CloudTrail as an
    independent mirror (docs/DEPLOYMENT.md). The append-only contract is the part
    that must not change."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> AuditRecord:
        self._records.append(record)
        return record

    def records(self, incident_ref: str | None = None, limit: int = 100) -> list[AuditRecord]:
        rows = self._records
        if incident_ref is not None:
            rows = [r for r in rows if r.incident_ref == incident_ref]
        return list(reversed(rows[-limit:]))

    def __len__(self) -> int:
        return len(self._records)


AUDIT = AuditLog()
