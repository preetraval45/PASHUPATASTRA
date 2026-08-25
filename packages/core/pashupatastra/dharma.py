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


class ActionDomain(StrEnum):
    """What kind of system an action operates on.

    A deployment serves one domain. The registry holds both because some actions
    belong to both — reading an entity's logs is the same act whichever question
    prompted it — and because deleting the infrastructure set to present a
    security console would throw away executors verified against a live cluster.
    """

    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"


class ActionSpec(BaseModel):
    """A registered action. Actions come from this closed registry, never from
    parsed model text (the Grounding ADR)."""

    id: str
    description: str
    base_risk: int = Field(ge=0, le=100)
    expected_post_state: dict[str, str]
    rollback_action_id: str | None = None
    irreversible: bool = False

    domains: frozenset[ActionDomain] = frozenset({ActionDomain.INFRASTRUCTURE})
    """Which domains this action belongs to. A set rather than one value: a few
    actions are genuinely shared, and duplicating them under two ids would give
    the policy engine two risk scores for one act."""

    read_only: bool = False
    """Whether this action only *reads*. Declared, never inferred.

    `changes_nothing` is a different question and a weaker one. It asks whether
    an act carries risk the policy engine should price, and by that measure
    paging an analyst is free — nothing breaks, nothing needs rolling back. But
    it wakes a person up, and `create_case` writes a record that outlives the
    request. Neither is read-only.

    The distinction exists because the two are used for opposite purposes.
    `changes_nothing` widens what may run unattended; this narrows what may be
    handed to a model. Deriving the second from the first would put "page the
    on-call analyst" behind an unauthenticated text box.
    """

    @property
    def has_tested_rollback(self) -> bool:
        return self.rollback_action_id is not None and not self.irreversible

    @property
    def changes_nothing(self) -> bool:
        """Whether performing this action alters no state.

        Zero risk *and* no expected post-state. Both halves are load-bearing:
        risk 0 alone would exempt an action somebody scored optimistically, and
        an empty post-state alone would exempt one that changes something its
        author simply failed to declare. Requiring the pair means an action
        escapes the rollback rule only by admitting it has nothing to verify.
        """
        return self.base_risk == 0 and not self.expected_post_state and not self.irreversible


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


class RiskFactor(StrEnum):
    """The named inputs risk is priced from.

    Every adjustment and every tier escalation carries one, so the arithmetic
    and the explanation of it share a vocabulary rather than each inventing
    their own words for the same term.
    """

    BLAST_RADIUS = "blast_radius"
    CONFIDENCE = "confidence"
    NOVELTY = "novelty"
    """Whether this action has been run here, and how it went when it was."""

    REVERSIBILITY = "reversibility"
    ENVIRONMENT = "environment"
    AGENT_LIMIT = "agent_limit"


class RiskAdjustment(BaseModel):
    reason: str
    delta: int
    factor: RiskFactor


class TierStep(BaseModel):
    """One rule that fired while the tier was being decided.

    The first step is always the risk band; the rest are the hard overrides, in
    the order `evaluate` applies them. `from_tier` equal to `to_tier` means the
    rule fired and the tier was already there — an independent reason for the
    outcome, not a step that did nothing.
    """

    rule: str
    factor: RiskFactor | None = None
    """None for the risk band, which is the score rather than any one factor."""

    detail: str
    from_tier: Tier
    to_tier: Tier


class Verdict(BaseModel):
    """Required argument to any execution. Carries its own reasoning."""

    action_id: str
    incident_ref: str | None
    base_risk: int
    adjustments: list[RiskAdjustment]
    effective_risk: int
    tier: Tier
    tier_reasons: list[TierStep] = Field(default_factory=list)
    """How this tier was arrived at, emitted by the branches that arrived at it.

    An approval surface has to answer "why does this need me?", and the honest
    answer is often not the score: an action of risk 12 with no tested rollback
    needs an operator, and a panel showing only the arithmetic leaves that
    looking like a bug. Restating the rules in the dashboard would fix the
    display and introduce a second answer, so the engine says it instead.
    """

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


APPROVERS: dict[Tier, list[str]] = {
    Tier.AUTONOMOUS: [],
    Tier.APPROVAL: ["operator"],
    Tier.SENIOR: ["senior_operator"],
    Tier.DENIED: [],
}
"""Who may authorise each tier. Lifted out of `evaluate` so that anything
describing the policy reads the same table the engine decides with — a page
restating these from memory is a second answer to "who may approve this", and
the day they disagree the wrong one is on the marketing site."""


def policy_model() -> dict[str, object]:
    """The policy in the shape a reader needs, generated rather than written.

    Exists because a page explaining the risk tiers must not restate them. The
    numbers here are the ones `_tier_for` branches on and the approvers are the
    ones `evaluate` attaches, so the table on the site cannot drift from the
    engine without the drift being a code change in one place.
    """
    return {
        "tiers": [
            {
                "tier": str(tier),
                "max_risk": ceiling,
                "min_risk": 0 if index == 0 else _TIERS[index - 1][0] + 1,
                "approvers": APPROVERS[tier],
            }
            for index, (ceiling, tier) in enumerate(_TIERS)
        ],
        "escalation": {
            "blast_radius_entities": BLAST_RADIUS_ESCALATION_ENTITIES,
            "blast_radius_users": BLAST_RADIUS_ESCALATION_USERS,
        },
    }


def _band(risk: int) -> tuple[int, int, Tier]:
    """The band a score falls in: its floor, its ceiling, and its tier."""
    floor = 0
    for ceiling, tier in _TIERS:
        if risk <= ceiling:
            return floor, ceiling, tier
        floor = ceiling + 1
    return floor, 100, Tier.DENIED


def _tier_for(risk: int) -> Tier:
    return _band(risk)[2]


def _escalate(tier: Tier) -> Tier:
    order = [Tier.AUTONOMOUS, Tier.APPROVAL, Tier.SENIOR, Tier.DENIED]
    return order[min(order.index(tier) + 1, len(order) - 1)]


class _Ladder:
    """The tier and the record of how it got there, moved together.

    Kept as a class so that changing the tier without saying why is not
    something `evaluate` can express. The alternative — assigning to a local and
    building the explanation afterwards from the same conditions — is two
    implementations of one decision, and the day they disagree the panel tells
    an operator the wrong reason for the request in front of them.
    """

    def __init__(self, tier: Tier, detail: str) -> None:
        self.tier = tier
        self.steps = [
            TierStep(rule="risk_band", factor=None, detail=detail, from_tier=tier, to_tier=tier)
        ]

    def apply(self, tier: Tier, *, rule: str, factor: RiskFactor, detail: str) -> None:
        self.steps.append(
            TierStep(rule=rule, factor=factor, detail=detail, from_tier=self.tier, to_tier=tier)
        )
        self.tier = tier


def score(action: ActionSpec, context: RiskContext) -> tuple[int, list[RiskAdjustment]]:
    """Compute effective risk. Adjustments are additive and never negative."""
    adjustments: list[RiskAdjustment] = []

    if context.blast_radius_entities > 1:
        adjustments.append(
            RiskAdjustment(
                reason=f"blast radius: {context.blast_radius_entities} entities",
                delta=min(context.blast_radius_entities * 3, 20),
                factor=RiskFactor.BLAST_RADIUS,
            )
        )
    if context.blast_radius_users > 100:
        adjustments.append(
            RiskAdjustment(
                reason=f"blast radius: ~{context.blast_radius_users} users",
                delta=min(context.blast_radius_users // 200, 15),
                factor=RiskFactor.BLAST_RADIUS,
            )
        )
    if context.environment is Environment.PROD:
        adjustments.append(
            RiskAdjustment(reason="production environment", delta=15, factor=RiskFactor.ENVIRONMENT)
        )
    elif context.environment is Environment.STAGING:
        adjustments.append(
            RiskAdjustment(reason="staging environment", delta=5, factor=RiskFactor.ENVIRONMENT)
        )

    if context.diagnostic_confidence < 0.8:
        adjustments.append(
            RiskAdjustment(
                reason=f"low diagnostic confidence ({context.diagnostic_confidence:.2f})",
                delta=int((0.8 - context.diagnostic_confidence) * 50),
                factor=RiskFactor.CONFIDENCE,
            )
        )
    if not context.executed_here_before:
        adjustments.append(
            RiskAdjustment(
                reason="never executed in this environment", delta=10, factor=RiskFactor.NOVELTY
            )
        )
    if context.failed_here_before:
        # Capped so a run of failures cannot on its own push an action to DENIED
        # — that call belongs to the tier thresholds, not to this term.
        adjustments.append(
            RiskAdjustment(
                reason=f"failed here {context.failed_here_before}× before",
                delta=min(context.failed_here_before * 8, 24),
                factor=RiskFactor.NOVELTY,
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
    floor, ceiling, band = _band(effective)
    ladder = _Ladder(band, f"effective risk {effective} falls in the {floor}–{ceiling} band")
    denial: str | None = None

    # Hard overrides — applied regardless of the computed score.
    if action.irreversible:
        ladder.apply(
            Tier.DENIED,
            rule="irreversible",
            factor=RiskFactor.REVERSIBILITY,
            detail=f"{action.id} is declared irreversible, so no score puts it "
            "within reach of automation",
        )
        denial = "irreversible actions are never autonomous"
    elif not action.has_tested_rollback and not action.changes_nothing:
        # "No tested rollback cannot be autonomous" is a rule about actions that
        # change something. Reading a log changes nothing, so there is nothing
        # to undo and nothing to verify, and demanding an undo it cannot have
        # made the whole 0-30 band unreachable for every read-only action —
        # which is to say, made diagnosis itself require an approval.
        ladder.apply(
            _escalate(ladder.tier),
            rule="no_tested_rollback",
            factor=RiskFactor.REVERSIBILITY,
            detail=f"{action.id} changes state and declares no tested rollback",
        )
    if ladder.tier is not Tier.DENIED and (
        context.blast_radius_entities >= BLAST_RADIUS_ESCALATION_ENTITIES
        or context.blast_radius_users >= BLAST_RADIUS_ESCALATION_USERS
    ):
        reach = []
        if context.blast_radius_entities >= BLAST_RADIUS_ESCALATION_ENTITIES:
            reach.append(
                f"{context.blast_radius_entities} entities "
                f"(escalates at {BLAST_RADIUS_ESCALATION_ENTITIES})"
            )
        if context.blast_radius_users >= BLAST_RADIUS_ESCALATION_USERS:
            reach.append(
                f"~{context.blast_radius_users} users "
                f"(escalates at {BLAST_RADIUS_ESCALATION_USERS})"
            )
        ladder.apply(
            _escalate(ladder.tier),
            rule="blast_radius",
            factor=RiskFactor.BLAST_RADIUS,
            detail="reaches " + " and ".join(reach),
        )
    if (
        agent_risk_limit is not None
        and effective > agent_risk_limit
        and ladder.tier is not Tier.DENIED
    ):
        denial = f"effective risk {effective} exceeds agent risk limit {agent_risk_limit}"
        ladder.apply(
            Tier.DENIED,
            rule="agent_risk_limit",
            factor=RiskFactor.AGENT_LIMIT,
            detail=denial,
        )

    tier = ladder.tier
    approvers = APPROVERS[tier]

    now = datetime.now().astimezone()
    return Verdict(
        action_id=action.id,
        incident_ref=incident_ref,
        base_risk=action.base_risk,
        adjustments=adjustments,
        effective_risk=effective,
        tier=tier,
        tier_reasons=ladder.steps,
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
