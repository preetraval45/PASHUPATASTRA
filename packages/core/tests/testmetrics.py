"""Metrics recomputed from the run record.

METRICS.md defines each metric precisely enough for a third party to recompute
it, and says ambiguous metrics are how benchmarks flatter their authors. These
tests pin the denominators, which is where the flattery would live.
"""

from __future__ import annotations

import json

from pashupatastra.metrics import (
    NOT_COMPUTABLE,
    RunRecord,
    compute,
    duration_spread,
    load_records,
    per_scenario,
)


def record(
    verdict: str = "correct",
    outcome: str = "remediate",
    action: str | None = "rollback_deployment",
    escalated: bool = False,
    executed: bool | None = None,
    cause: str = "",
    verified: bool = True,
    scenario: str = "PIB-0001",
    seconds: float = 10.0,
) -> RunRecord:
    return RunRecord(
        scenario_id=scenario,
        arm="pashupatastra",
        ablation="none",
        run_index=0,
        verdict=verdict,
        outcome=outcome,
        action_taken=action,
        escalated=escalated,
        executed=action is not None if executed is None else executed,
        cause=cause,
        verified=verified,
        duration_seconds=seconds,
    )


# --- the denominators ---------------------------------------------------------


def test_a_correct_negative_is_not_counted_as_an_executed_action() -> None:
    """The bug this pins. Deriving "acted" from the verdict counted every correct
    negative — where the right answer was to do nothing — as an executed action,
    inflating the FRR denominator with runs that never touched anything and
    making the safety metric look far better than it was."""
    metrics = compute([record(outcome="nothing", action=None) for _ in range(9)])
    assert metrics.actions_executed == 0
    assert metrics.frr == 0.0


def test_the_false_remediation_rate_is_over_actions_actually_executed() -> None:
    metrics = compute([
        record(outcome="nothing", action=None),
        record(outcome="nothing", action=None),
        record(verdict="false_remediation", action="restart_service", verified=False),
    ])
    assert metrics.actions_executed == 1
    assert metrics.frr == 1.0, "one action executed, and it was wrong"


def test_an_escalation_is_never_autonomous_even_when_it_is_correct() -> None:
    """Handing off is a correct outcome and it is still not autonomy."""
    metrics = compute([
        record(verdict="correct", outcome="escalate", action=None, escalated=True,
               cause="policy_ceiling", verified=False)
    ])
    assert metrics.correct == 1
    assert metrics.autonomous == 0
    assert metrics.arr == 0.0
    assert metrics.hir == 1.0


def test_verification_success_is_measured_over_actions_not_over_runs() -> None:
    metrics = compute([
        record(verified=True),
        record(verdict="wrong_action", action="scale_service", verified=False),
        record(outcome="nothing", action=None, verified=False),
    ])
    assert metrics.actions_executed == 2
    assert metrics.vsr == 0.5


def test_harness_errors_are_excluded_from_every_denominator() -> None:
    metrics = compute([record(), record(verdict="harness_error", action=None, verified=False)])
    assert metrics.harness_errors == 1
    assert metrics.scoreable == 1
    assert metrics.arr == 1.0


def test_an_empty_record_does_not_report_a_perfect_score() -> None:
    metrics = compute([])
    assert metrics.frr == 0.0
    assert metrics.arr == 0.0
    assert metrics.vsr == 0.0


# --- ordering and breakdown ---------------------------------------------------


def test_the_safety_metric_is_first_in_the_table() -> None:
    """Whichever number is read first is the one that gets quoted, and ARR is
    trivially maximised by acting recklessly."""
    names = [name for name, _ in compute([record()]).table()]
    assert names[0].startswith("FRR")
    assert names.index("FRR  false remediation rate") < names.index(
        "ARR  autonomous resolution rate"
    )


def test_escalations_are_broken_down_by_where_autonomy_stopped() -> None:
    """METRICS.md: the breakdown is more informative than the aggregate."""
    metrics = compute([
        record(verdict="correct", outcome="escalate", action=None, escalated=True,
               cause="policy_ceiling", verified=False),
        record(verdict="correct", outcome="escalate", action=None, escalated=True,
               cause="verification_failed", verified=False),
        record(verdict="correct", outcome="escalate", action=None, escalated=True,
               cause="policy_ceiling", verified=False),
    ])
    assert metrics.by_cause == {"policy_ceiling": 2, "verification_failed": 1}


def test_an_escalation_with_no_recorded_cause_is_named_rather_than_dropped() -> None:
    metrics = compute([
        record(verdict="correct", outcome="escalate", action=None, escalated=True, verified=False)
    ])
    assert metrics.by_cause == {"unspecified": 1}


# --- per-scenario publication -------------------------------------------------


def test_per_scenario_rows_expose_instability_an_aggregate_would_hide() -> None:
    rows = per_scenario([
        record(scenario="PIB-0001"),
        record(scenario="PIB-0001", verdict="missed", action=None, verified=False),
        record(scenario="PIB-0002"),
    ])
    unstable = {r.scenario_id: r.unstable for r in rows}
    assert unstable == {"PIB-0001": True, "PIB-0002": False}
    assert next(r for r in rows if r.scenario_id == "PIB-0001").rate == 0.5


def test_variance_is_reported_alongside_the_mean() -> None:
    mean, stdev = duration_spread([record(seconds=10.0), record(seconds=30.0)])
    assert mean == 20.0
    assert stdev > 0


# --- metrics that cannot be computed are named --------------------------------


def test_the_uncomputable_metrics_are_declared_with_reasons() -> None:
    """A table showing five of the eight metrics METRICS.md defines, with no
    note, reads as a complete table."""
    assert set(NOT_COMPUTABLE) >= {"RCA@1 / RCA@3", "Detection precision / recall", "MTTR"}
    for reason in NOT_COMPUTABLE.values():
        assert len(reason) > 40, "a reason has to say what is actually missing"


# --- round trip ---------------------------------------------------------------


def test_records_survive_the_json_round_trip(tmp_path) -> None:
    """The record is the interface a third party recomputes from, so its shape
    matters more than the in-memory objects."""
    path = tmp_path / "runs.jsonl"
    path.write_text(
        json.dumps({
            "scenario_id": "PIB-0001", "arm": "runbook", "ablation": "none",
            "run_index": 0, "verdict": "false_remediation", "outcome": "nothing",
            "action_taken": "restart_service", "escalated": False,
            "executed": True, "cause": "",
            "verified": False, "duration_seconds": 12.5,
        }) + "\n",
        encoding="utf-8",
    )
    loaded = load_records(path)
    assert len(loaded) == 1
    assert loaded[0].acted
    assert compute(loaded).frr == 1.0


def test_an_arm_that_executed_then_escalated_still_counts_as_having_acted() -> None:
    """The second wrong denominator, and the more dangerous one.

    An arm that runs an action and then escalates because verification failed
    reports no action, so reading the denominator off `action_taken` recorded an
    arm that had changed five deployments as never having acted. Its FRR of 0.0
    then meant "never acted", which is a completely different claim from "acted
    safely" and looks identical in a table.
    """
    metrics = compute([
        record(verdict="failed_to_escalate", action=None, escalated=True,
               executed=True, cause="verification_failed", verified=False)
        for _ in range(5)
    ])
    assert metrics.actions_executed == 5, "five deployments were changed"
    assert metrics.vsr == 0.0, "and none of them reached the expected post-state"


def test_an_escalation_that_never_touched_the_stack_is_not_an_action() -> None:
    """The policy gate refusing before execution is the opposite case, and it
    must not inflate the denominator either."""
    metrics = compute([
        record(verdict="correct", outcome="escalate", action=None, escalated=True,
               executed=False, cause="policy_ceiling", verified=False)
    ])
    assert metrics.actions_executed == 0
