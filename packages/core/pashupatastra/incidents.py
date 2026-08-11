"""Incident model (v0). See docs/specs/Incident Model.md.

An incident is the unit of work: many events, one causal chain, one plan, one
verification record. State is the fold of its transitions, never edited in place.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from .dharma import Verdict
from .events import EntityRef


class IncidentState(StrEnum):
    DETECTED = "detected"
    CORRELATED = "correlated"
    DIAGNOSED = "diagnosed"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    VERIFICATION_FAILED = "verification_failed"
    ROLLED_BACK = "rolled_back"
    ESCALATED = "escalated"


class IncidentSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Transition(BaseModel):
    """Append-only. Every state change names its actor and justification."""

    at: datetime
    from_state: IncidentState | None
    to_state: IncidentState
    actor: str
    justification: str


class Hypothesis(BaseModel):
    """A causal explanation.

    `evidence` is required and non-empty: a hypothesis that cannot cite the
    telemetry supporting it is suppressed, not surfaced at low confidence
    (the Grounding ADR). `contradicted_by` lets the system show its own doubt.
    """

    statement: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(min_length=1)
    contradicted_by: list[str] = Field(default_factory=list)
    mechanism: list[str] = Field(default_factory=list)

    @field_validator("evidence")
    @classmethod
    def _evidence_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("hypothesis without evidence must be suppressed, not surfaced")
        return v


class CausalLink(BaseModel):
    entity: EntityRef
    transition: str
    evidence: list[str] = Field(min_length=1)


class Impact(BaseModel):
    estimated_users_affected: int = 0
    affected_services: list[str] = Field(default_factory=list)
    blast_radius_entities: int = 0


class PlanStep(BaseModel):
    order: int
    action_id: str
    expected_post_state: dict[str, str]
    rollback_action_id: str | None = None
    verdict: Verdict | None = None


class Execution(BaseModel):
    step_order: int
    action_id: str
    started_at: datetime
    finished_at: datetime | None = None
    succeeded: bool | None = None
    output: str | None = None
    verdict_snapshot: Verdict


class VerificationCheck(BaseModel):
    name: str
    expected: str
    observed: str | None = None
    passed: bool | None = None


class Verification(BaseModel):
    """Observational, never model-judged (the Grounding ADR)."""

    window_seconds: int
    checks: list[VerificationCheck] = Field(default_factory=list)
    completed_at: datetime | None = None

    @property
    def passed(self) -> bool | None:
        if not self.checks or any(c.passed is None for c in self.checks):
            return None
        return all(c.passed for c in self.checks)


class Incident(BaseModel):
    id: str
    state: IncidentState = IncidentState.DETECTED
    severity: IncidentSeverity
    opened_at: datetime
    closed_at: datetime | None = None
    affected_entities: list[EntityRef] = Field(default_factory=list)
    impact: Impact = Field(default_factory=Impact)
    event_ids: list[str] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    causal_chain: list[CausalLink] = Field(default_factory=list)
    plan: list[PlanStep] = Field(default_factory=list)
    executions: list[Execution] = Field(default_factory=list)
    verification: Verification | None = None
    similar_incident_ids: list[str] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)

    @property
    def top_hypothesis(self) -> Hypothesis | None:
        return max(self.hypotheses, key=lambda h: h.confidence, default=None)

    @property
    def resolved_autonomously(self) -> bool:
        """True only if no human touched it — used by the ARR benchmark metric."""
        if self.state is not IncidentState.RESOLVED:
            return False
        return all(t.actor.startswith("agent:") or t.actor == "dharma" for t in self.transitions)

    def transition_to(self, state: IncidentState, actor: str, justification: str) -> None:
        self.transitions.append(
            Transition(
                at=datetime.now().astimezone(),
                from_state=self.state,
                to_state=state,
                actor=actor,
                justification=justification,
            )
        )
        self.state = state


def incident_id(year: int, sequence: int) -> str:
    return f"INC-{year}-{sequence:04d}"
