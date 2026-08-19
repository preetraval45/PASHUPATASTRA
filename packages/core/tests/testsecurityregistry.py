"""The blue-team action registry, and the refusals that must hold in it.

The registry is the closed set an incident may draw from. Two properties matter
more than the contents: that nothing catastrophic is ever autonomous, and that
every rollback an action names actually exists — a plan whose undo does not
resolve fails at the exact moment the undo is needed.
"""

from __future__ import annotations

import pytest
from pashupatastra import Environment, RiskContext, Tier, evaluate
from pashupatastra.dharma import ActionDomain
from pashupatastra.registry import all_actions, get

SECURITY = all_actions(ActionDomain.SECURITY)

NEVER_AUTONOMOUS = ("wipe_host", "rotate_credentials", "force_password_reset")
"""Irreversible, so no verification result can justify them running unattended."""


def context(**overrides: object) -> RiskContext:
    base: dict[str, object] = {
        "environment": Environment.PROD,
        "blast_radius_entities": 0,
        "blast_radius_users": 0,
        "diagnostic_confidence": 1.0,
        "executed_here_before": True,
        "dry_run": False,
    }
    base.update(overrides)
    return RiskContext(**base)  # type: ignore[arg-type]


# --- the refusals -------------------------------------------------------------


@pytest.mark.parametrize("action_id", NEVER_AUTONOMOUS)
@pytest.mark.parametrize("confidence", [0.0, 0.5, 0.9, 0.99, 1.0])
@pytest.mark.parametrize("environment", list(Environment))
def test_irreversible_actions_are_never_autonomous(
    action_id: str, confidence: float, environment: Environment
) -> None:
    """Certainty is not permission. A confident diagnosis lowers effective risk,
    and there is no amount of it that should let something unrecoverable run
    without a human — the whole point of the tier is that the system can be
    confidently wrong."""
    verdict = evaluate(
        get(action_id),
        context(diagnostic_confidence=confidence, environment=environment),
    )
    assert verdict.tier is Tier.DENIED
    assert verdict.denial_reason


def test_wiping_a_host_is_denied_even_with_an_enormous_blast_radius() -> None:
    """Blast radius escalates a tier; it must never de-escalate one."""
    verdict = evaluate(
        get("wipe_host"),
        context(blast_radius_entities=500, blast_radius_users=100_000),
    )
    assert verdict.tier is Tier.DENIED


def test_containment_of_an_account_needs_a_human() -> None:
    """Disabling an account at risk 45 lands above the autonomous band. An
    analyst locked out by a false positive is the cost being priced."""
    verdict = evaluate(get("disable_account"), context())
    assert verdict.tier is not Tier.AUTONOMOUS


def test_read_only_actions_are_never_denied() -> None:
    """Reading is never refused outright, whatever tier it lands in."""
    for action_id in ("read_logs", "query_threat_intel", "notify_analyst", "create_case"):
        verdict = evaluate(get(action_id), context())
        assert verdict.tier is not Tier.DENIED, action_id


def test_read_only_actions_are_not_yet_autonomous() -> None:
    """Asserts what the engine currently does, which is not what the registry
    implies it should.

    A risk-0 action with no post-state changes nothing, so it has nothing to
    roll back — but `evaluate` escalates every action lacking a rollback, and
    the 0-30 autonomous band is therefore unreachable for all four read-only
    actions in every environment. Registering them at risk 0 buys nothing today.

    Left asserting reality rather than the intent, because relaxing the rule is
    a change to the safety core and belongs to whoever owns that decision. See
    R4b in docs/REBUILD.md — R19's read-only agent tools depend on the answer.
    """
    for action_id in ("read_logs", "query_threat_intel", "notify_analyst", "create_case"):
        verdict = evaluate(get(action_id), context())
        assert verdict.tier is Tier.APPROVAL, action_id


# --- the registry's own consistency -------------------------------------------


def test_every_declared_rollback_is_registered() -> None:
    """An undo that does not resolve fails at the moment it is needed, which is
    the worst possible time to discover it."""
    registered = {a.id for a in all_actions()}
    for action in all_actions():
        if action.rollback_action_id is not None:
            assert action.rollback_action_id in registered, action.id


def test_rollbacks_are_mutual() -> None:
    """If A undoes B, B undoes A. A one-way pair leaves the loop unable to
    return to where it started."""
    for action in SECURITY:
        undo_id = action.rollback_action_id
        if undo_id is None:
            continue
        assert get(undo_id).rollback_action_id == action.id, action.id


def test_undoing_containment_is_not_discounted() -> None:
    """Restoring a cache is benign, so `warm_cache` scores below `clear_cache`.
    Security inverts that: putting a possibly-compromised host back on the
    network is about as dangerous as taking it off, and scoring the undo lower
    would let the riskier direction through on the cheaper verdict."""
    for action in SECURITY:
        undo_id = action.rollback_action_id
        if undo_id is None:
            continue
        assert get(undo_id).base_risk >= action.base_risk, (
            f"{undo_id} is cheaper than {action.id}"
        )


def test_every_risky_action_declares_an_undo_or_admits_it_has_none() -> None:
    for action in SECURITY:
        if action.base_risk > 0:
            assert action.rollback_action_id or action.irreversible, action.id


def test_isolating_a_host_keeps_edr_reachable() -> None:
    """A machine nobody can inspect cannot be cleared, and cannot be watched
    while somebody decides. The post-state is what verification checks, so the
    requirement has to live there rather than in the description."""
    assert get("isolate_host").expected_post_state["edr"] == "reachable"


# --- domains ------------------------------------------------------------------


def test_the_security_domain_excludes_infrastructure_actions() -> None:
    ids = {a.id for a in SECURITY}
    assert {"isolate_host", "block_ip", "revoke_session"} <= ids
    assert not ids & {"restart_service", "scale_service", "rollback_deployment"}


def test_reading_logs_belongs_to_both_domains() -> None:
    """The same act whichever question prompted it. A second id would give the
    policy engine two risk scores for one thing."""
    action = get("read_logs")
    assert action.domains == {ActionDomain.INFRASTRUCTURE, ActionDomain.SECURITY}


def test_filtering_does_not_narrow_what_resolves() -> None:
    """A plan written against one domain must stay executable when a deployment
    presents the other — including its rollbacks."""
    assert get("restart_service").id == "restart_service"
    assert get("isolate_host").id == "isolate_host"
