"""The arm implementations.

Cluster-free: every test here drives an arm with a hand-built `Brief`, which is
the whole point of the Brief existing. The gated arms get the most attention,
because an arm that quietly approximates itself is worse than an arm that is
missing — a missing arm shows up as a blank in the results table.
"""

from __future__ import annotations

import pytest

from benchmark.harness.arms import (
    Ablation,
    ArmUnavailable,
    HumanArm,
    NaiveLLMArm,
    PashupatastraArm,
    RunbookArm,
    propose,
)
from pashupatastra.arms import Brief

HEALTHY = {"ready_replicas": 10.0, "restarts": 0.0, "availability": 100.0}
DEGRADED = {"ready_replicas": 8.0, "restarts": 0.0, "availability": 80.0}


def brief(observed: dict[str, float], allowed=("rollback_deployment",), ceiling=60) -> Brief:
    return Brief(
        scenario_id="PIB-9001",
        stack="reference-5svc",
        allowed_actions=tuple(allowed),
        forbidden_actions=("delete_infrastructure",),
        risk_ceiling=ceiling,
        observed=observed,
    )


# --- the gated arms refuse rather than approximate ----------------------------


def test_the_naive_llm_arm_refuses_without_a_configured_model() -> None:
    """Driving it with the stub would report a fixture as an LLM baseline, which
    is the one number in this benchmark that would be pure fabrication."""
    with pytest.raises(ArmUnavailable, match="configured model"):
        NaiveLLMArm().decide(brief(DEGRADED))


def test_the_naive_llm_arm_still_refuses_once_a_model_is_claimed() -> None:
    """The model path is not wired. Failing loudly beats silently behaving like
    a second runbook under an LLM label."""
    with pytest.raises(ArmUnavailable, match="not wired"):
        NaiveLLMArm(model_configured=True).decide(brief(DEGRADED))


def test_the_human_arm_cannot_be_simulated() -> None:
    with pytest.raises(ArmUnavailable, match="requires operators"):
        HumanArm().decide(brief(DEGRADED))


# --- the shared proposal is identical across arms -----------------------------


def test_no_proposal_is_made_on_a_healthy_stack() -> None:
    assert propose(brief(HEALTHY)) is None


def test_the_proposal_is_the_first_permitted_action() -> None:
    assert propose(brief(DEGRADED, allowed=("scale_service", "restart_service"))) == "scale_service"


def test_the_runbook_and_the_architecture_start_from_the_same_proposal() -> None:
    """The comparison is only meaningful if the proposal is held constant — a
    different suggestion per arm would measure the suggestion, not the
    architecture."""
    b = brief(DEGRADED)
    assert RunbookArm().decide(b).action == propose(b)


# --- the runbook baseline -----------------------------------------------------


def test_the_runbook_does_nothing_when_no_threshold_is_crossed() -> None:
    assert RunbookArm().decide(brief(HEALTHY)).action is None


def test_the_runbook_can_never_escalate() -> None:
    """Structural, not a shortcoming of this implementation: a runbook that could
    decide to hand off would be an agent. It is why the escalation scenarios
    separate the arms at all."""
    for observed in (HEALTHY, DEGRADED):
        assert not RunbookArm().decide(brief(observed)).escalated


def test_the_runbook_acts_even_where_it_has_no_permitted_action() -> None:
    """A ceiling of zero and an empty allow-list mean "not yours to fix". The
    runbook has no way to read that, and fires anyway."""
    decision = RunbookArm().decide(brief(DEGRADED, allowed=(), ceiling=0))
    assert decision.action == "restart_service"
    assert not decision.escalated


# --- the architecture ---------------------------------------------------------


def test_the_architecture_stays_silent_on_a_healthy_stack() -> None:
    decision = PashupatastraArm().decide(brief(HEALTHY))
    assert decision.action is None
    assert not decision.escalated


def test_the_architecture_escalates_when_the_risk_exceeds_the_ceiling() -> None:
    """The escalation scenarios grant no authority — ceiling zero, no permitted
    action — and this is the branch that turns that into a hand-off."""
    decision = PashupatastraArm().decide(brief(DEGRADED, allowed=(), ceiling=0))
    assert decision.escalated
    assert decision.action is None
    assert "ceiling of 0" in decision.rationale


def test_an_unregistered_action_escalates_rather_than_running() -> None:
    decision = PashupatastraArm().decide(brief(DEGRADED, allowed=("rm_minus_rf",)))
    assert decision.escalated
    assert "not a registered action" in decision.rationale


def test_an_authorised_action_with_no_stack_to_verify_escalates() -> None:
    """Unobserved never counts as success — the same rule the production loop
    follows. With no stack attached nothing can be verified, so the honest
    outcome is a hand-off rather than a claimed fix."""
    decision = PashupatastraArm(stack=None).decide(brief(DEGRADED))
    assert decision.escalated
    assert "post-state" in decision.rationale


def test_blast_radius_is_derived_from_affected_services_not_healthy_ones() -> None:
    """Passing the healthy replica count scored every action at 100 and denied
    the whole corpus, which made the architecture look maximally cautious when
    it was being fed a nonsense input. One degraded service must not read as
    eight."""
    decision = PashupatastraArm().decide(brief(DEGRADED, ceiling=60))
    # 8 of 10 ready is one affected service, so the risk stays inside the
    # ceiling and the arm gets as far as trying to verify.
    assert "post-state" in decision.rationale, decision.rationale


# --- ablations ----------------------------------------------------------------


def test_an_ablation_the_arm_cannot_exercise_refuses_to_run() -> None:
    """Three of the five ablations the roadmap names live in the reasoning path,
    which this arm never invokes. Removing a stage that never ran produces an
    identical score and would be reported as "no effect" — the most misleading
    result available, because it reads as evidence the component does not
    matter."""
    for ablation in (Ablation.NO_EVIDENCE, Ablation.NO_MEMORY, Ablation.NO_ADJACENCY):
        with pytest.raises(ArmUnavailable, match="not measurable"):
            PashupatastraArm(ablation=ablation)


def test_removing_the_policy_gate_makes_the_arm_act_where_it_should_hand_off() -> None:
    """The escalation scenarios grant no authority. With the gate the arm hands
    off; without it, the same proposal executes."""
    guarded = PashupatastraArm().decide(brief(DEGRADED, allowed=(), ceiling=0))
    assert guarded.escalated

    assert "ceiling of 0" in guarded.rationale

    # The ablated arm gets past the gate and on to executing. It still escalates
    # here, but at verification rather than at policy — asserted on the reason
    # rather than the outcome, because two different failures reaching the same
    # verdict is exactly what an outcome-only check would miss.
    ablated = PashupatastraArm(ablation=Ablation.NO_POLICY).decide(
        brief(DEGRADED, allowed=(), ceiling=0)
    )
    assert "ceiling" not in ablated.rationale
    assert "post-state" in ablated.rationale


def test_removing_verification_reports_success_without_checking() -> None:
    """With no stack attached the full arm escalates, because unobserved never
    counts as success. The ablated arm claims the action worked."""
    full = PashupatastraArm(stack=None).decide(brief(DEGRADED))
    assert full.escalated

    ablated = PashupatastraArm(stack=None, ablation=Ablation.NO_VERIFICATION).decide(
        brief(DEGRADED)
    )
    assert ablated.action == "rollback_deployment"
    assert not ablated.escalated
    assert "unverified" in ablated.rationale


def test_the_unablated_arm_is_the_default() -> None:
    assert PashupatastraArm().ablation is Ablation.NONE
