"""Policy tests. Every tier needs a denial test (docs/CONTRIBUTING.md)."""

from __future__ import annotations

import pytest

from pashupatastra import Environment, PolicyViolation, RiskContext, Tier, evaluate, require_verdict
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
