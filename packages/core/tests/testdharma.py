"""Policy tests. Every tier needs a denial test (docs/CONTRIBUTING.md)."""

from __future__ import annotations

import pytest

from pashupatastra import (
    ActionSpec,
    Environment,
    PolicyViolation,
    RiskContext,
    RiskFactor,
    Tier,
    evaluate,
    require_verdict,
)
from pashupatastra.dharma import BLAST_RADIUS_ESCALATION_ENTITIES, _tier_for
from pashupatastra.registry import get


def ctx(**kwargs: object) -> RiskContext:
    base: dict[str, object] = {"environment": Environment.DEV}
    base.update(kwargs)
    return RiskContext.model_validate(base)


def test_low_risk_action_is_autonomous() -> None:
    verdict = evaluate(get("restart_service"), ctx())
    assert verdict.tier is Tier.AUTONOMOUS
    assert verdict.is_executable


def test_rollback_in_prod_requires_approval() -> None:
    verdict = evaluate(get("rollback_deployment"), ctx(environment=Environment.PROD))
    assert verdict.tier is Tier.APPROVAL
    assert not verdict.is_executable, "approval tier must not execute without a grant"


def test_db_config_change_reaches_senior_tier() -> None:
    verdict = evaluate(get("modify_db_config"), ctx(environment=Environment.PROD))
    assert verdict.tier is Tier.SENIOR


def test_irreversible_action_is_always_denied() -> None:
    verdict = evaluate(get("delete_infrastructure"), ctx())
    assert verdict.tier is Tier.DENIED
    assert not verdict.is_executable


def test_adjustments_never_lower_risk() -> None:
    action = get("rollback_deployment")
    verdict = evaluate(action, ctx(environment=Environment.PROD, blast_radius_entities=4))
    assert verdict.effective_risk >= action.base_risk
    assert all(a.delta >= 0 for a in verdict.adjustments)


def test_large_blast_radius_escalates_a_tier() -> None:
    small = evaluate(get("restart_service"), ctx())
    large = evaluate(get("restart_service"), ctx(blast_radius_entities=8))
    assert small.tier is Tier.AUTONOMOUS
    assert large.tier is not Tier.AUTONOMOUS


def test_low_confidence_raises_risk() -> None:
    confident = evaluate(get("restart_service"), ctx(diagnostic_confidence=1.0))
    unsure = evaluate(get("restart_service"), ctx(diagnostic_confidence=0.3))
    assert unsure.effective_risk > confident.effective_risk


def test_agent_risk_limit_denies_even_approved_tiers() -> None:
    verdict = evaluate(get("rollback_deployment"), ctx(), agent_risk_limit=40)
    assert verdict.tier is Tier.DENIED
    assert verdict.denial_reason is not None


def test_execution_without_verdict_raises() -> None:
    with pytest.raises(PolicyViolation):
        require_verdict(None, get("restart_service"))


def test_verdict_for_a_different_action_is_rejected() -> None:
    verdict = evaluate(get("restart_service"), ctx())
    with pytest.raises(PolicyViolation):
        require_verdict(verdict, get("rollback_deployment"))


def test_expired_verdict_is_not_executable() -> None:
    from datetime import datetime, timedelta

    verdict = evaluate(get("restart_service"), ctx())
    verdict.expires_at = datetime.now().astimezone() - timedelta(seconds=1)
    assert not verdict.is_executable


def test_every_registered_action_has_rollback_or_is_irreversible() -> None:
    from pashupatastra.registry import all_actions

    for action in all_actions():
        if action.base_risk > 0:
            assert action.rollback_action_id or action.irreversible, action.id


# ------------------------------------------------------------------ R65: why this tier
#
# The approval panel explains why an action needs a human. The explanation is
# only worth showing if it cannot disagree with the decision it explains, so
# these tests check the two ways it could: a step nobody recorded, and a chain
# that ends somewhere other than the tier.


def every_context() -> list[RiskContext]:
    """A spread wide enough to reach every tier by every route."""
    return [
        ctx(),
        ctx(environment=Environment.STAGING),
        ctx(environment=Environment.PROD),
        ctx(blast_radius_entities=8),
        ctx(blast_radius_users=4000),
        ctx(environment=Environment.PROD, blast_radius_entities=12, blast_radius_users=9000),
        ctx(diagnostic_confidence=0.1),
        ctx(executed_here_before=False),
        ctx(failed_here_before=3),
        ctx(environment=Environment.PROD, diagnostic_confidence=0.2, failed_here_before=5),
    ]


def test_the_tier_reasons_end_at_the_tier() -> None:
    """The explanation cannot disagree with the verdict it explains."""
    from pashupatastra.registry import all_actions

    for action in all_actions():
        for context in every_context():
            for limit in (None, 20):
                verdict = evaluate(action, context, agent_risk_limit=limit)
                assert verdict.tier_reasons, f"{action.id} arrived at {verdict.tier} silently"
                assert verdict.tier_reasons[-1].to_tier is verdict.tier


def test_the_tier_reasons_are_a_chain() -> None:
    """Each step starts where the last one ended — no gaps, no reordering."""
    from pashupatastra.registry import all_actions

    for action in all_actions():
        for context in every_context():
            steps = evaluate(action, context).tier_reasons
            for earlier, later in zip(steps, steps[1:]):
                assert later.from_tier is earlier.to_tier
            assert steps[0].rule == "risk_band"
            assert steps[0].from_tier is steps[0].to_tier


def test_the_first_step_is_the_band_the_score_falls_in() -> None:
    verdict = evaluate(get("modify_db_config"), ctx(environment=Environment.PROD))
    band = verdict.tier_reasons[0]
    assert str(verdict.effective_risk) in band.detail
    assert band.to_tier is _tier_for(verdict.effective_risk)


def test_a_tier_above_the_band_names_the_rule_that_raised_it() -> None:
    """The case the score alone cannot explain.

    An action can score in the autonomous band and still need an operator,
    because it changes something it cannot undo. A panel showing only the
    arithmetic makes that look like a bug in the arithmetic.

    Built by hand rather than taken from the registry: every registered action
    has a rollback or is irreversible, so nothing shipped reaches this branch.
    The branch is still what decides the tier for anything added later.
    """
    action = ActionSpec(
        id="drain_queue",
        description="drain the dead-letter queue",
        base_risk=10,
        expected_post_state={"queue.depth": "0"},
    )
    verdict = evaluate(action, ctx())
    assert verdict.tier is not _tier_for(verdict.effective_risk)
    step = next(s for s in verdict.tier_reasons if s.rule == "no_tested_rollback")
    assert step.factor is RiskFactor.REVERSIBILITY
    assert "drain_queue" in step.detail
    assert step.to_tier is verdict.tier


def test_the_blast_radius_step_names_the_threshold_it_crossed() -> None:
    verdict = evaluate(get("restart_service"), ctx(blast_radius_entities=8))
    step = next(s for s in verdict.tier_reasons if s.rule == "blast_radius")
    assert "8 entities" in step.detail
    assert str(BLAST_RADIUS_ESCALATION_ENTITIES) in step.detail


def test_a_denial_the_score_did_not_cause_says_so() -> None:
    verdict = evaluate(get("force_password_reset"), ctx())
    assert _tier_for(verdict.effective_risk) is Tier.AUTONOMOUS
    step = verdict.tier_reasons[-1]
    assert step.rule == "irreversible"
    assert step.factor is RiskFactor.REVERSIBILITY
    assert step.from_tier is Tier.AUTONOMOUS and step.to_tier is Tier.DENIED


def test_a_rule_that_fires_without_moving_the_tier_is_still_recorded() -> None:
    """An independent reason for the outcome is not a step that did nothing.

    `delete_infrastructure` scores 100, so the band denies it before the
    irreversibility rule is reached. Recording only steps that move the tier
    would have the panel explain that denial as a high number, when the real
    reason is that there is no way back and no score would have helped.
    """
    verdict = evaluate(get("delete_infrastructure"), ctx())
    assert _tier_for(verdict.effective_risk) is Tier.DENIED
    step = verdict.tier_reasons[-1]
    assert step.rule == "irreversible"
    assert step.from_tier is step.to_tier is Tier.DENIED


def test_every_adjustment_names_the_factor_it_prices() -> None:
    """The arithmetic and the explanation share a vocabulary."""
    from pashupatastra.registry import all_actions

    for action in all_actions():
        for context in every_context():
            for adjustment in evaluate(action, context).adjustments:
                assert isinstance(adjustment.factor, RiskFactor)
