"""The LLM baseline arms (RP-07, adr/LLMBaselines), against scripted gateways.

The four properties the plan names: both refuse on the stub; neither sees the
expected answer; a schema-invalid reply is an error, not an answer; an off-list
proposal is rejected. Plus: the LLM replaces the proposer only — Dharma still
gates what it proposes.
"""

from __future__ import annotations

import dataclasses

import pytest
from pashupatastra.arms import Brief
from pashupatastra.gateway import ModelResponse, SchemaViolation, Usage

from benchmark.harness.arms import ArmUnavailable, NaiveLLMArm, PashupatastraArm
from benchmark.harness.llm import LLMProposer, Proposal, render


class Scripted:
    """A gateway whose provider answers from a script."""

    def __init__(self, output=None, error=None, model="qwen2.5:7b"):
        self.output, self.error = output, error
        self.provider = type("P", (), {"model": model, "name": "scripted"})()
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return ModelResponse(output=self.output, usage=Usage(), model=self.provider.model,
                             provider="scripted", purpose=request.purpose)


def brief(**observed) -> Brief:
    return Brief(
        scenario_id="PIB-0042",
        stack="kind",
        allowed_actions=("rollback_deployment", "scale_service"),
        forbidden_actions=("delete_namespace",),
        risk_ceiling=60,
        observed=observed or {"availability": 40.0},
    )


def test_both_llm_arms_refuse_the_stub():
    stub = LLMProposer(Scripted(output={"action": "do_nothing", "reason": ""}, model="echo-0"))
    with pytest.raises(ArmUnavailable):
        NaiveLLMArm(stub).decide(brief())
    with pytest.raises(ArmUnavailable):
        PashupatastraArm(proposer=stub).decide(brief())
    with pytest.raises(ArmUnavailable):
        NaiveLLMArm(None).decide(brief())


def test_the_model_never_sees_the_expected_answer():
    gateway = Scripted(output={"action": "do_nothing", "reason": "fine"})
    LLMProposer(gateway).propose(brief())
    text = gateway.requests[0].evidence[0].content
    assert "expected" not in text.lower()
    # Only the Brief's own fields, which are what every arm sees.
    assert {f.name for f in dataclasses.fields(Brief)} >= {"scenario_id", "observed", "allowed_actions"}
    assert render(brief()) == text


def test_a_schema_invalid_reply_is_an_error_not_an_answer():
    proposal = LLMProposer(Scripted(error=SchemaViolation("not JSON"))).propose(brief())
    assert proposal == Proposal(action=None, escalate=True, cause="llm_error", reason="not JSON")


def test_an_off_list_proposal_is_rejected():
    proposal = LLMProposer(Scripted(output={"action": "delete_namespace", "reason": "x"})).propose(brief())
    assert proposal.action is None and proposal.escalate and proposal.cause == "off_list"


def test_the_naive_arm_runs_whatever_the_model_proposes():
    arm = NaiveLLMArm(LLMProposer(Scripted(output={"action": "scale_service", "reason": "r"})))
    decision = arm.decide(brief())
    assert decision.action == "scale_service" and decision.executed


def test_do_nothing_and_escalate_are_answers():
    nothing = NaiveLLMArm(LLMProposer(Scripted(output={"action": "do_nothing", "reason": "healthy"}))).decide(brief())
    assert nothing.action is None and not nothing.escalated
    handoff = NaiveLLMArm(LLMProposer(Scripted(output={"action": "escalate", "reason": "risky"}))).decide(brief())
    assert handoff.escalated and handoff.cause == "model_escalated"


def test_the_full_arm_still_puts_the_proposal_through_dharma():
    """A ceiling of 0 forbids everything; the LLM's proposal must be stopped
    by policy, exactly as the deterministic one would be."""
    tight = dataclasses.replace(brief(), risk_ceiling=0)
    arm = PashupatastraArm(proposer=LLMProposer(Scripted(output={"action": "rollback_deployment", "reason": "r"})))
    decision = arm.decide(tight)
    assert decision.escalated and decision.cause == "policy_ceiling"
    assert not decision.executed
