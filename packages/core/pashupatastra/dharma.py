"""Dharma — the policy engine. Bounded autonomy, enforced structurally.

The core rule (docs/specs/Policy%20Model.md):

    Astra cannot execute without a Dharma verdict.

This module owns risk scoring and verdict issuance. It is deterministic code by
design — no model call participates in authorization (the Grounding ADR).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field

VERDICT_TTL = timedelta(minutes=15)
"""Verdicts are short-lived: a plan approved during an incident must not be
replayable later against different system state."""


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Tier(StrEnum):
    AUTONOMOUS = "autonomous"
    APPROVAL = "approval"
    SENIOR = "senior"
    DENIED = "denied"


class ActionSpec(BaseModel):
    """A registered action. Actions come from this closed registry, never from
    parsed model text (the Grounding ADR)."""

    id: str
    description: str
    base_risk: int = Field(ge=0, le=100)
    expected_post_state: dict[str, str]
    rollback_action_id: str | None = None
    irreversible: bool = False

    @property
    def has_tested_rollback(self) -> bool:
        return self.rollback_action_id is not None and not self.irreversible


class RiskContext(BaseModel):
    """Everything that can raise an action's risk above its declared base."""

    environment: Environment
    blast_radius_entities: int = 0
    blast_radius_users: int = 0
    diagnostic_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    executed_here_before: bool = True
    failed_here_before: int = Field(default=0, ge=0)
    """Prior failures of this action in this environment. An action that has been
    tried here and did not work is riskier than one never tried."""

    dry_run: bool = True


class RiskAdjustment(BaseModel):
    reason: str
    delta: int


class Verdict(BaseModel):
    """Required argument to any execution. Carries its own reasoning."""

    action_id: str
    incident_ref: str | None
    base_risk: int
    adjustments: list[RiskAdjustment]
    effective_risk: int
    tier: Tier
    required_approvers: list[str]
    granted_by: str | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    constraints: dict[str, str] = Field(default_factory=dict)
    denial_reason: str | None = None

    @property
    def is_executable(self) -> bool:
        if self.tier is Tier.DENIED:
            return False
        if self.tier is not Tier.AUTONOMOUS and self.granted_by is None:
            return False
        if self.expires_at is not None and datetime.now().astimezone() > self.expires_at:
            return False
        return True


# Thresholds from docs/specs/Policy Model.md. Adjustments only ever raise risk —
# an action cannot argue its way into a lower tier.
_TIERS: list[tuple[int, Tier]] = [
    (30, Tier.AUTONOMOUS),
    (60, Tier.APPROVAL),
    (80, Tier.SENIOR),
    (100, Tier.DENIED),
]

BLAST_RADIUS_ESCALATION_ENTITIES = 5
BLAST_RADIUS_ESCALATION_USERS = 1000


def _tier_for(risk: int) -> Tier:
    for ceiling, tier in _TIERS:
        if risk <= ceiling:
            return tier
    return Tier.DENIED


def _escalate(tier: Tier) -> Tier:
    order = [Tier.AUTONOMOUS, Tier.APPROVAL, Tier.SENIOR, Tier.DENIED]
    return order[min(order.index(tier) + 1, len(order) - 1)]


def score(action: ActionSpec, context: RiskContext) -> tuple[int, list[RiskAdjustment]]:
    """Compute effective risk. Adjustments are additive and never negative."""
    adjustments: list[RiskAdjustment] = []

    if context.blast_radius_entities > 1:
        adjustments.append(
            RiskAdjustment(
                reason=f"blast radius: {context.blast_radius_entities} entities",
                delta=min(context.blast_radius_entities * 3, 20),
            )
        )
    if context.blast_radius_users > 100:
        adjustments.append(
            RiskAdjustment(
                reason=f"blast radius: ~{context.blast_radius_users} users",
                delta=min(context.blast_radius_users // 200, 15),
            )
        )
    if context.environment is Environment.PROD:
        adjustments.append(RiskAdjustment(reason="production environment", delta=15))
    elif context.environment is Environment.STAGING:
        adjustments.append(RiskAdjustment(reason="staging environment", delta=5))

    if context.diagnostic_confidence < 0.8:
        adjustments.append(
            RiskAdjustment(
                reason=f"low diagnostic confidence ({context.diagnostic_confidence:.2f})",
                delta=int((0.8 - context.diagnostic_confidence) * 50),
            )
        )
    if not context.executed_here_before:
        adjustments.append(RiskAdjustment(reason="never executed in this environment", delta=10))
    if context.failed_here_before:
        # Capped so a run of failures cannot on its own push an action to DENIED
        # — that call belongs to the tier thresholds, not to this term.
        adjustments.append(
            RiskAdjustment(
                reason=f"failed here {context.failed_here_before}× before",
                delta=min(context.failed_here_before * 8, 24),
            )
        )

    effective = min(action.base_risk + sum(a.delta for a in adjustments), 100)
    return effective, adjustments


def evaluate(
    action: ActionSpec,
    context: RiskContext,
    incident_ref: str | None = None,
    agent_risk_limit: int | None = None,
) -> Verdict:
    """Issue a verdict. This is the only way to obtain authorization to execute."""
    effective, adjustments = score(action, context)
    tier = _tier_for(effective)
    denial: str | None = None

    # Hard overrides — applied regardless of the computed score.
    if action.irreversible:
        tier, denial = Tier.DENIED, "irreversible actions are never autonomous"
    elif not action.has_tested_rollback:
        tier = _escalate(tier)
        if tier is Tier.AUTONOMOUS:
            tier = Tier.APPROVAL
    if tier is not Tier.DENIED and (
        context.blast_radius_entities >= BLAST_RADIUS_ESCALATION_ENTITIES
        or context.blast_radius_users >= BLAST_RADIUS_ESCALATION_USERS
    ):
        tier = _escalate(tier)
    if agent_risk_limit is not None and effective > agent_risk_limit and tier is not Tier.DENIED:
        tier = Tier.DENIED
        denial = f"effective risk {effective} exceeds agent risk limit {agent_risk_limit}"

    approvers = {
        Tier.AUTONOMOUS: [],
        Tier.APPROVAL: ["operator"],
        Tier.SENIOR: ["senior_operator"],
        Tier.DENIED: [],
    }[tier]

    now = datetime.now().astimezone()
    return Verdict(
        action_id=action.id,
        incident_ref=incident_ref,
        base_risk=action.base_risk,
        adjustments=adjustments,
        effective_risk=effective,
        tier=tier,
        required_approvers=list(approvers),
        granted_by="dharma" if tier is Tier.AUTONOMOUS else None,
        granted_at=now if tier is Tier.AUTONOMOUS else None,
        expires_at=now + VERDICT_TTL,
        constraints={"dry_run": str(context.dry_run).lower()},
        denial_reason=denial,
    )


class PolicyViolation(Exception):
    """Raised when execution is attempted without a valid verdict."""


def require_verdict(verdict: Verdict | None, action: ActionSpec) -> Verdict:
    """Guard every execution path. There is no bypass, including in test fixtures."""
    if verdict is None:
        raise PolicyViolation(f"no verdict supplied for action {action.id}")
    if verdict.action_id != action.id:
        raise PolicyViolation(f"verdict is for {verdict.action_id}, not {action.id}")
    if not verdict.is_executable:
        raise PolicyViolation(
            f"verdict for {action.id} is not executable "
            f"(tier={verdict.tier}, granted_by={verdict.granted_by})"
        )
    return verdict
