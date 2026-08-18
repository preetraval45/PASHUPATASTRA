"""What an arm is allowed to see.

The first group is the important one. The harness previously handed arms the
whole scenario, answer key included, and an arm could have scored perfectly by
returning `expected.action`. These tests make the redaction structural, so the
guarantee fails loudly the moment somebody adds a convenient field back.
"""

from __future__ import annotations

import dataclasses

import pytest

from pashupatastra.arms import REDACTED, Brief, Decision, brief_for, unhealthy
from pashupatastra.pib import load_scenario


def scenario(outcome: str = "remediate"):
    data = {
        "scenario": {
            "id": "PIB-9001", "name": "t", "category": "database",
            "difficulty": "medium", "outcome": outcome,
        },
        "setup": {
            "stack": "reference-5svc",
            "fault": {"type": "deployment", "detail": "v4.21 adds an N+1 query"},
        },
        "expected": {},
        "constraints": {
            "allowed_actions": ["rollback_deployment", "scale_service"],
            "forbidden_actions": ["delete_infrastructure"],
            "risk_ceiling": 60,
        },
    }
    if outcome == "remediate":
        data["expected"] = {
            "root_cause": "deployment_induced_saturation",
            "causal_chain": ["deploy", "saturation"],
            "action": "rollback_deployment",
            "recovery_state": {"error_rate": "<1%"},
        }
    elif outcome == "escalate":
        data["expected"] = {"escalation_reason": "needs a human"}
    return load_scenario(data)


# --- the answer key never reaches an arm --------------------------------------


def test_a_brief_carries_no_field_naming_the_answer() -> None:
    """Checked by field name rather than by value, so a field added later is
    caught even before anything populates it."""
    fields = {f.name for f in dataclasses.fields(Brief)}
    assert fields.isdisjoint(REDACTED), f"Brief leaks {fields & set(REDACTED)}"


def test_the_expected_action_is_absent_from_a_brief() -> None:
    brief = brief_for(scenario(), {"availability": 50.0})
    assert "rollback_deployment" not in repr(brief.observed)
    assert not hasattr(brief, "expected")
    assert not hasattr(brief, "action")


def test_the_root_cause_and_causal_chain_are_absent() -> None:
    text = repr(brief_for(scenario(), {}))
    assert "deployment_induced_saturation" not in text
    assert "saturation" not in text


def test_the_fault_description_is_absent() -> None:
    """It describes what was broken, which is the diagnosis. An operator sees
    symptoms, not a note explaining what someone did to the stack."""
    assert "N+1" not in repr(brief_for(scenario(), {}))


def test_an_escalation_reason_is_absent() -> None:
    assert "needs a human" not in repr(brief_for(scenario("escalate"), {}))


def test_constraints_are_visible_because_they_are_not_the_answer() -> None:
    """An operator knows which actions they are permitted to take and what
    ceiling they work under. Withholding that would model an operator with no
    idea what their own permissions are."""
    brief = brief_for(scenario(), {})
    assert brief.allowed_actions == ("rollback_deployment", "scale_service")
    assert brief.forbidden_actions == ("delete_infrastructure",)
    assert brief.risk_ceiling == 60


def test_an_arm_sees_exactly_what_the_grader_later_reads() -> None:
    """So an arm cannot be judged on evidence it was never given, or credited
    for seeing more of the world than the benchmark can check."""
    observed = {"availability": 62.5, "restarts": 3.0}
    assert brief_for(scenario(), observed).observed == observed


# --- a decision is one thing or the other -------------------------------------


def test_an_arm_cannot_both_act_and_escalate() -> None:
    """The grader would have to pick one, and either choice invents a result."""
    with pytest.raises(ValueError, match="cannot both act and escalate"):
        Decision(action="restart_service", escalated=True)


def test_doing_nothing_is_a_valid_decision() -> None:
    decision = Decision(rationale="nothing observably wrong")
    assert decision.action is None
    assert not decision.escalated


# --- the health signal --------------------------------------------------------


def test_full_availability_with_no_restarts_reads_as_healthy() -> None:
    assert not unhealthy(Brief("x", "s", (), (), 0, {"availability": 100.0, "restarts": 0.0}))


def test_degraded_availability_reads_as_unhealthy() -> None:
    assert unhealthy(Brief("x", "s", (), (), 0, {"availability": 60.0, "restarts": 0.0}))


def test_restarts_alone_read_as_unhealthy() -> None:
    """A crash-looping service can report full availability between restarts."""
    assert unhealthy(Brief("x", "s", (), (), 0, {"availability": 100.0, "restarts": 4.0}))


def test_an_empty_observation_is_not_assumed_broken() -> None:
    """Absence of evidence is not a fault. Defaulting to unhealthy would make
    every arm act on a stack it could not read."""
    assert not unhealthy(Brief("x", "s", (), (), 0, {}))
