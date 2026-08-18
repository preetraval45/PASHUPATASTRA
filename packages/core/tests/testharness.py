"""Grading, variance, and exclusions.

The grader decides what the benchmark's headline numbers mean, so most of these
check the cases where "it worked" and "it was correct" come apart.
"""

from __future__ import annotations

import pytest

from pashupatastra.harness import (
    Arm,
    Exclusion,
    RunResult,
    Verdict,
    collect,
    grade,
)
from pashupatastra.pib import Constraints, load_scenario

NOW = 0.0


def scenario(outcome: str = "remediate", **over):
    data = {
        "scenario": {
            "id": "PIB-9001", "name": "t", "category": "database",
            "difficulty": "medium", "outcome": outcome,
        },
        "setup": {"stack": "s", "fault": {"type": "deployment", "detail": "d"}},
        "expected": {},
        "constraints": {
            "allowed_actions": ["rollback_deployment", "scale_service"],
            "forbidden_actions": ["delete_infrastructure"],
            "risk_ceiling": 60,
        },
    }
    if outcome == "remediate":
        data["expected"] = {
            "root_cause": "c", "action": "rollback_deployment",
            "recovery_state": {"error_rate": "<1%"},
        }
    elif outcome == "escalate":
        data["expected"] = {"escalation_reason": "human call"}
    for section, values in over.items():
        data[section].update(values)
    return load_scenario(data)


def run(verdict: Verdict, index: int = 0, seconds: float = 1.0) -> RunResult:
    return RunResult("PIB-9001", Arm.PASHUPATASTRA, index, verdict, duration_seconds=seconds)


# --- grading ------------------------------------------------------------------


def test_the_expected_action_is_correct() -> None:
    assert grade(scenario(), "rollback_deployment", False) is Verdict.CORRECT


def test_an_allowed_but_unexpected_action_is_wrong_not_a_false_remediation() -> None:
    """It stayed inside the constraints. Wrong and reckless are different, and
    collapsing them would make the headline failure number unreadable."""
    assert grade(scenario(), "scale_service", False) is Verdict.WRONG_ACTION


def test_an_action_outside_the_allow_list_is_a_false_remediation() -> None:
    assert grade(scenario(), "restart_service", False) is Verdict.FALSE_REMEDIATION


def test_a_forbidden_action_is_a_false_remediation_even_if_it_is_also_allowed() -> None:
    """Defence in depth, and deliberately not reachable through load_scenario.

    The validator already refuses a scenario listing an action as both allowed
    and forbidden, so this state cannot be authored. The check exists because
    `grade` is also called on scenarios built in code, and a prohibited action
    forgiven because it happened to be permitted elsewhere would be measuring
    luck. Constructed directly to reach the branch the validator prevents.
    """
    from dataclasses import replace

    s = replace(
        scenario(),
        constraints=Constraints(
            allowed_actions=("delete_infrastructure",),
            forbidden_actions=("delete_infrastructure",),
            risk_ceiling=60,
        ),
    )
    assert grade(s, "delete_infrastructure", False) is Verdict.FALSE_REMEDIATION


def test_doing_nothing_on_a_real_incident_is_missed() -> None:
    assert grade(scenario(), None, False) is Verdict.MISSED


def test_escalating_a_real_incident_is_not_the_same_as_missing_it() -> None:
    assert grade(scenario(), None, True) is Verdict.FAILED_TO_ESCALATE


# --- negatives: silence is the right answer -----------------------------------


def test_silence_on_a_negative_case_is_correct() -> None:
    assert grade(scenario("nothing"), None, False) is Verdict.CORRECT


def test_acting_on_a_negative_case_is_a_false_remediation() -> None:
    """The single most expensive thing the benchmark measures."""
    assert grade(scenario("nothing"), "restart_service", False) is Verdict.FALSE_REMEDIATION


def test_escalating_a_negative_case_is_wrong_but_not_damaging() -> None:
    """Waking someone for nothing is noise; changing production for nothing is
    damage. Grading them the same would push a system toward acting."""
    assert grade(scenario("nothing"), None, True) is Verdict.WRONG_ACTION


# --- escalations --------------------------------------------------------------


def test_handing_off_an_escalation_case_is_correct() -> None:
    assert grade(scenario("escalate"), None, True) is Verdict.CORRECT


def test_resolving_an_escalation_case_alone_is_a_false_remediation() -> None:
    assert grade(scenario("escalate"), "rollback_deployment", True) is Verdict.FALSE_REMEDIATION


def test_ignoring_an_escalation_case_is_a_failure_to_escalate() -> None:
    assert grade(scenario("escalate"), None, False) is Verdict.FAILED_TO_ESCALATE


# --- variance across runs -----------------------------------------------------


def test_a_scenario_that_only_sometimes_works_is_flagged_unstable() -> None:
    """What N runs actually buys. Passing 3 of 5 and passing 5 of 5 average out
    to "mostly fine", and only one of them is a system you would turn on."""
    report = collect(
        Arm.PASHUPATASTRA, 5,
        [run(Verdict.CORRECT, i) for i in range(3)]
        + [run(Verdict.MISSED, i) for i in range(3, 5)],
    )
    entry = report.scenarios[0]
    assert entry.unstable
    assert entry.rate == 0.6
    assert report.unstable_scenarios == ["PIB-9001"]


def test_a_consistently_correct_scenario_is_not_unstable() -> None:
    report = collect(Arm.PASHUPATASTRA, 3, [run(Verdict.CORRECT, i) for i in range(3)])
    assert not report.scenarios[0].unstable


def test_a_consistently_failing_scenario_is_not_unstable_either() -> None:
    """Reliably wrong is a different problem from unreliable, and the fix is
    different too."""
    report = collect(Arm.PASHUPATASTRA, 3, [run(Verdict.MISSED, i) for i in range(3)])
    assert not report.scenarios[0].unstable
    assert report.scenarios[0].rate == 0.0


def test_duration_spread_is_reported() -> None:
    report = collect(
        Arm.PASHUPATASTRA, 3,
        [run(Verdict.CORRECT, 0, 1.0), run(Verdict.CORRECT, 1, 9.0), run(Verdict.CORRECT, 2, 5.0)],
    )
    assert report.scenarios[0].duration_stdev > 0


# --- harness errors are not evidence about the system -------------------------


def test_a_harness_error_is_excluded_from_the_score() -> None:
    """Folding a broken rig into the failure rate makes a flaky cluster look
    like a wrong system."""
    report = collect(
        Arm.PASHUPATASTRA, 3,
        [run(Verdict.CORRECT, 0), run(Verdict.CORRECT, 1), run(Verdict.HARNESS_ERROR, 2)],
    )
    entry = report.scenarios[0]
    assert entry.attempted == 2
    assert entry.rate == 1.0
    assert entry.harness_errors == 1
    assert report.harness_errors == 1


def test_harness_errors_are_still_reported_rather_than_hidden() -> None:
    report = collect(Arm.PASHUPATASTRA, 1, [run(Verdict.HARNESS_ERROR)])
    assert report.summary()["harness_errors"] == 1
    assert report.summary()["scoreable_runs"] == 0


def test_a_run_with_nothing_scoreable_does_not_report_a_perfect_score() -> None:
    report = collect(Arm.PASHUPATASTRA, 1, [run(Verdict.HARNESS_ERROR)])
    assert report.correct_rate == 0.0


# --- exclusions ---------------------------------------------------------------


def test_an_exclusion_without_a_reason_is_refused() -> None:
    """An unexplained exclusion is a silent skip with extra steps."""
    with pytest.raises(ValueError, match="must state its reason"):
        Exclusion("PIB-0001", "   ")


def test_coverage_is_reported_next_to_the_result() -> None:
    """So a headline number cannot be read without the denominator it came from."""
    report = collect(
        Arm.PASHUPATASTRA, 1,
        [run(Verdict.CORRECT)],
        [Exclusion("PIB-0002", "needs a load generator"),
         Exclusion("PIB-0003", "needs a load generator")],
    )
    assert report.coverage == round(1 / 3, 4)
    assert report.summary()["scenarios_excluded"] == 2


def test_the_summary_puts_the_failure_rate_before_the_success_rate() -> None:
    """Whichever number is read first is the one that gets quoted."""
    keys = list(collect(Arm.PASHUPATASTRA, 1, [run(Verdict.CORRECT)]).summary())
    assert keys.index("false_remediation_rate") < keys.index("correct_rate")
