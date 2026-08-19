"""The scripted blue-team scenarios.

What is worth testing about written fixtures is not their contents — those are
whatever someone typed — but the properties that make them honest: every
citation resolves, every contradiction names the evidence that does the
contradicting, and the plans draw only on actions the registry actually holds.

The scenarios exist to show reasoning, so a scenario whose reasoning does not
hold together is worse than none.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from app.demoincidents import scenarios
from pashupatastra import IncidentState, Tier, RiskContext, Environment, evaluate
from pashupatastra.registry import get as get_action

NOW = datetime(2026, 8, 19, 12, 0, 0).astimezone()
SCENARIOS = scenarios(NOW)
BY_ID = {s.incident.id: s for s in SCENARIOS}


def cited(scenario) -> set[str]:
    incident = scenario.incident
    ids = {e for h in incident.hypotheses for e in h.evidence}
    ids |= {e for h in incident.hypotheses for e in h.contradicted_by}
    ids |= {e for link in incident.causal_chain for e in link.evidence}
    return ids


@pytest.fixture(params=SCENARIOS, ids=lambda s: s.incident.id)
def scenario(request):
    return request.param


# --- the properties that make a written scenario honest -----------------------


def test_every_cited_evidence_id_exists(scenario) -> None:
    """A citation that resolves to nothing is worse than no citation: it looks
    checkable, so a reader stops looking."""
    assert cited(scenario) <= {signal.id for signal in scenario.signals}


def test_no_signal_is_unused(scenario) -> None:
    """Telemetry nothing cites is set dressing. If it is in the store it should
    be doing work in the argument."""
    unused = {s.id for s in scenario.signals} - cited(scenario)
    assert not unused, f"uncited signals: {sorted(unused)}"


def test_the_alternative_is_contradicted_by_named_evidence(scenario) -> None:
    """Every scenario carries a reading that is genuinely reasonable and turns
    out to be wrong, and it must be *ruled out* rather than merely outscored.
    A hypothesis dismissed by having a lower confidence is a preference; one
    dismissed by evidence is a finding."""
    alternatives = [h for h in scenario.incident.hypotheses[1:]]
    assert alternatives, "a scenario with no alternative demonstrates no reasoning"
    for alternative in alternatives:
        assert alternative.contradicted_by, alternative.statement
        assert alternative.confidence < scenario.incident.hypotheses[0].confidence


def test_every_causal_step_carries_a_technique(scenario) -> None:
    """These are all adversary behaviour, so every step has a mapping. The field
    is optional in the model for infrastructure incidents, not for these."""
    for link in scenario.incident.causal_chain:
        assert link.attack_technique is not None, link.transition


def test_plans_use_registered_actions_only(scenario) -> None:
    for step in scenario.incident.plan:
        action = get_action(step.action_id)
        assert step.expected_post_state == action.expected_post_state
        assert step.rollback_action_id == action.rollback_action_id


def test_every_plan_reaches_a_human_somewhere(scenario) -> None:
    """Not every step needs approval — forcing a re-authentication is cheap and
    reversible, and holding it for a click would be theatre. What must be true
    is that no plan completes without a human, which is why each incident sits
    in `awaiting_approval` or `escalated` rather than resolving itself."""
    tiers = [
        evaluate(get_action(step.action_id), RiskContext(environment=Environment.PROD)).tier
        for step in scenario.incident.plan
    ]
    assert any(tier is not Tier.AUTONOMOUS for tier in tiers), scenario.incident.id


def test_no_plan_step_is_denied(scenario) -> None:
    """A plan containing something policy forbids is not a plan, it is a wish.
    Nothing irreversible belongs in one for the same reason."""
    for step in scenario.incident.plan:
        action = get_action(step.action_id)
        assert not action.irreversible, step.action_id
        verdict = evaluate(action, RiskContext(environment=Environment.PROD))
        assert verdict.tier is not Tier.DENIED, step.action_id


def test_events_declare_themselves_as_scripted(scenario) -> None:
    """Nothing here was observed. No view may present it as though it were."""
    for event in scenario.events(NOW):
        assert event.provenance.source_system == "demo-scenario"
        assert event.provenance.query == scenario.incident.id


def test_incidents_are_awaiting_a_human(scenario) -> None:
    assert scenario.incident.state in {
        IncidentState.AWAITING_APPROVAL,
        IncidentState.ESCALATED,
    }


# --- the specific point each scenario exists to make --------------------------


def test_token_theft_does_not_reset_the_password() -> None:
    """The distinction the scenario is built around. The password was never
    used, so resetting it inconveniences the user and leaves the stolen token
    working — the attacker keeps reading the mailbox and the alert closes."""
    plan = {step.action_id for step in BY_ID["INC-2026-0902"].incident.plan}
    assert "revoke_session" in plan
    assert "quarantine_email" in plan
    assert "force_password_reset" not in plan


def test_credential_stuffing_is_ruled_out_by_impossible_travel() -> None:
    """Travelling is an ordinary explanation for one sign-in from a new place.
    Only the interval separates it from a compromise."""
    incident = BY_ID["INC-2026-0901"].incident
    travelling = next(h for h in incident.hypotheses if "travelling" in h.statement)
    assert "SEC-0001-c" in travelling.contradicted_by


def test_beaconing_is_separated_from_backup_by_destination() -> None:
    """Regular outbound connections are what backup software looks like. The
    pattern does not distinguish them; the destination does."""
    incident = BY_ID["INC-2026-0903"].incident
    backup = next(h for h in incident.hypotheses if "backup" in h.statement)
    assert "SEC-0003-e" in backup.contradicted_by


def test_isolating_a_host_needs_senior_approval() -> None:
    verdict = evaluate(get_action("isolate_host"), RiskContext(environment=Environment.PROD))
    assert verdict.tier is Tier.SENIOR


def test_incident_ids_are_unique() -> None:
    ids = [s.incident.id for s in SCENARIOS]
    assert len(ids) == len(set(ids))
