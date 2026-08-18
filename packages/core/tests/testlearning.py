"""Learning from having acted.

The weight is on the asymmetry: a loop that records successes more readily than
failures grows more confident without growing more correct, and every test here
that looks redundant is checking that a failure survived.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pashupatastra.dharma import ActionSpec, Environment, RiskContext, Tier, evaluate, score
from pashupatastra.learning import (
    NOVELTY_HORIZON,
    EstimationError,
    ExecutionHistory,
    ExecutionRecord,
    Familiarity,
    Prediction,
    learn,
    report,
)
from pashupatastra.remediation import Disposition, Remediation
from pashupatastra.smriti import MemoryKind, Smriti, Trust

NOW = datetime(2026, 8, 18, 12, 0, 0).astimezone()


def an_action(base_risk: int = 10) -> ActionSpec:
    return ActionSpec(
        id="restart_service",
        description="test",
        base_risk=base_risk,
        expected_post_state={"health": "healthy"},
        rollback_action_id="restart_service",
    )


def a_remediation(disposition: Disposition) -> Remediation:
    return Remediation(
        action_id="restart_service",
        disposition=disposition,
        reason="test",
    )


def executed(
    disposition: Disposition = Disposition.RESOLVED,
    at: datetime = NOW,
    environment: Environment = Environment.PROD,
    predicted: Prediction | None = None,
    observed: Prediction | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        action_id="restart_service",
        environment=environment,
        at=at,
        disposition=disposition,
        predicted=predicted,
        observed=observed,
    )


def learned(disposition: Disposition) -> tuple[Smriti, ExecutionHistory]:
    memory, history = Smriti(), ExecutionHistory()
    learn(
        memory=memory,
        history=history,
        tenant="acme",
        incident_ref="INC-1",
        remediation=a_remediation(disposition),
        environment=Environment.PROD,
        now=NOW,
        summary="checkout latency spike after deploy",
        entities={"service:checkout"},
        signals={"latency_p99"},
    )
    return memory, history


# --- successes and failures with equal prominence -----------------------------


def test_a_failed_remediation_is_written_to_memory_at_all() -> None:
    """The one that a naive implementation drops."""
    memory, history = learned(Disposition.ROLLED_BACK)
    assert len(memory.recall("acme", "checkout latency", entities={"service:checkout"})) == 1
    assert len(history) == 1


def test_a_failure_is_stored_the_same_way_as_a_success() -> None:
    """Equal prominence has to be structural. A failure filed as a lesser kind, or
    with a shorter retention, is forgotten sooner than a success — which is the
    bias reappearing one layer down."""
    won, _ = learned(Disposition.RESOLVED)
    lost, _ = learned(Disposition.ROLLED_BACK)

    a = won.recall("acme", "checkout latency", entities={"service:checkout"})[0].record
    b = lost.recall("acme", "checkout latency", entities={"service:checkout"})[0].record
    assert a.kind is b.kind is MemoryKind.INCIDENT
    assert a.retention == b.retention
    assert a.trust is b.trust


def test_a_failed_outcome_carries_a_warning_for_recall() -> None:
    memory, _ = learned(Disposition.ROLLED_BACK)
    record = memory.recall("acme", "checkout latency", entities={"service:checkout"})[0].record
    assert record.outcome is not None
    assert record.outcome.resolved is False
    assert record.outcome.verification_passed is False
    assert record.outcome.warning is not None


def test_a_resolved_outcome_carries_no_warning() -> None:
    memory, _ = learned(Disposition.RESOLVED)
    record = memory.recall("acme", "checkout latency", entities={"service:checkout"})[0].record
    assert record.outcome is not None
    assert record.outcome.warning is None


def test_the_system_vouches_for_its_own_records() -> None:
    """Unlike an ingested runbook, nobody outside wrote this."""
    memory, _ = learned(Disposition.RESOLVED)
    record = memory.recall("acme", "checkout latency", entities={"service:checkout"})[0].record
    assert record.trust is Trust.VERIFIED


def test_an_escalation_is_recorded_as_a_non_success() -> None:
    _, history = learned(Disposition.ESCALATED)
    assert history.familiarity("restart_service", Environment.PROD, NOW) is Familiarity.ATTEMPTED


# --- novelty fed by history ---------------------------------------------------


def test_an_action_never_run_here_is_novel() -> None:
    history = ExecutionHistory()
    assert history.familiarity("restart_service", Environment.PROD, NOW) is Familiarity.NOVEL


def test_success_elsewhere_does_not_make_an_action_familiar_here() -> None:
    """Succeeding in dev says nothing about prod, and treating it as evidence is
    how an untested action runs autonomously against production."""
    history = ExecutionHistory()
    history.record(executed(environment=Environment.DEV))
    assert history.familiarity("restart_service", Environment.PROD, NOW) is Familiarity.NOVEL


def test_tried_and_failed_is_not_the_same_as_never_tried() -> None:
    history = ExecutionHistory()
    history.record(executed(Disposition.ROLLED_BACK))
    assert history.familiarity("restart_service", Environment.PROD, NOW) is Familiarity.ATTEMPTED


def test_one_success_among_failures_counts_as_proven() -> None:
    history = ExecutionHistory()
    history.record(executed(Disposition.ROLLED_BACK))
    history.record(executed(Disposition.RESOLVED))
    assert history.familiarity("restart_service", Environment.PROD, NOW) is Familiarity.PROVEN


def test_an_execution_past_the_horizon_stops_counting() -> None:
    """The infrastructure it succeeded against may no longer exist."""
    history = ExecutionHistory()
    history.record(executed(at=NOW - NOVELTY_HORIZON - timedelta(days=1)))
    assert history.familiarity("restart_service", Environment.PROD, NOW) is Familiarity.NOVEL


def test_a_context_with_no_history_gets_the_novelty_penalty() -> None:
    """RiskContext.executed_here_before defaults to True, so a caller who forgets
    to set it silently suppresses the penalty. Deriving it from history means the
    safe answer comes from absent evidence rather than from someone remembering."""
    history = ExecutionHistory()
    base = RiskContext(environment=Environment.PROD)
    assert base.executed_here_before is True

    context = history.context_for("restart_service", Environment.PROD, NOW, base)
    assert context.executed_here_before is False

    _, adjustments = score(an_action(), context)
    assert any("never executed" in a.reason for a in adjustments)


def test_prior_failures_raise_risk_above_a_clean_first_attempt() -> None:
    history = ExecutionHistory()
    for _ in range(2):
        history.record(executed(Disposition.ROLLED_BACK))

    context = history.context_for(
        "restart_service", Environment.PROD, NOW, RiskContext(environment=Environment.PROD)
    )
    assert context.failed_here_before == 2

    tried, _ = score(an_action(), context)
    fresh, _ = score(an_action(), RiskContext(environment=Environment.PROD))
    assert tried > fresh


def test_repeated_failure_can_push_an_action_out_of_autonomous() -> None:
    """The behaviour that makes this worth wiring: the loop stops quietly retrying
    something that keeps not working, and asks a human instead."""
    history = ExecutionHistory()
    for _ in range(3):
        history.record(executed(Disposition.ROLLED_BACK))

    context = history.context_for(
        "restart_service", Environment.PROD, NOW, RiskContext(environment=Environment.PROD)
    )
    assert evaluate(an_action(), RiskContext(environment=Environment.PROD)).tier is Tier.AUTONOMOUS
    assert evaluate(an_action(), context).tier is not Tier.AUTONOMOUS


def test_the_failure_penalty_is_capped() -> None:
    """A long run of failures should not on its own reach DENIED — that call
    belongs to the tier thresholds, not to this one term."""
    history = ExecutionHistory()
    for _ in range(50):
        history.record(executed(Disposition.ROLLED_BACK))

    context = history.context_for(
        "restart_service", Environment.PROD, NOW, RiskContext(environment=Environment.PROD)
    )
    _, adjustments = score(an_action(), context)
    penalty = next(a for a in adjustments if "failed here" in a.reason)
    assert penalty.delta == 24


# --- estimation error ---------------------------------------------------------


def test_no_graded_predictions_reports_nothing_rather_than_zero_error() -> None:
    """An empty record must not read as a perfect one."""
    history = ExecutionHistory()
    history.record(executed())
    error = history.estimation_error()
    assert error.samples == 0
    assert error.summary()["samples"] == 0


def test_underestimating_blast_radius_is_counted_separately() -> None:
    """The dangerous direction, and the reason this is not a mean absolute error:
    predicting 2 when it was 6 and predicting 6 when it was 2 are the same number
    and very different mistakes."""
    history = ExecutionHistory()
    history.record(
        executed(predicted=Prediction(entities=2, users=10), observed=Prediction(entities=6, users=90))
    )
    error = history.estimation_error()
    assert error.underestimates == 1
    assert error.overestimates == 0
    assert not error.calibrated
    assert error.worst_underestimate == 4


def test_overestimating_does_not_count_as_uncalibrated() -> None:
    history = ExecutionHistory()
    history.record(
        executed(predicted=Prediction(entities=8, users=99), observed=Prediction(entities=3, users=10))
    )
    error = history.estimation_error()
    assert error.overestimates == 1
    assert error.calibrated, "predicting too large is the safe direction"
    assert error.mean_signed_entities < 0


def test_opposite_errors_do_not_cancel_into_a_clean_bill() -> None:
    """Averaging alone would report these two as perfectly calibrated."""
    history = ExecutionHistory()
    history.record(
        executed(predicted=Prediction(entities=1, users=0), observed=Prediction(entities=5, users=0))
    )
    history.record(
        executed(predicted=Prediction(entities=5, users=0), observed=Prediction(entities=1, users=0))
    )
    error = history.estimation_error()
    assert error.mean_signed_entities == 0.0
    assert not error.calibrated
    assert error.underestimate_rate == 0.5


def test_an_exact_prediction_is_neither_over_nor_under() -> None:
    history = ExecutionHistory()
    history.record(
        executed(predicted=Prediction(entities=3, users=50), observed=Prediction(entities=3, users=50))
    )
    error = history.estimation_error()
    assert error.exact == 1
    assert error.calibrated


def test_estimation_error_can_be_scoped_to_one_action() -> None:
    history = ExecutionHistory()
    history.record(
        executed(predicted=Prediction(entities=1, users=0), observed=Prediction(entities=9, users=0))
    )
    history.record(
        ExecutionRecord(
            action_id="clear_cache",
            environment=Environment.PROD,
            at=NOW,
            disposition=Disposition.RESOLVED,
            predicted=Prediction(entities=2, users=0),
            observed=Prediction(entities=2, users=0),
        )
    )
    assert history.estimation_error("clear_cache").calibrated
    assert not history.estimation_error("restart_service").calibrated


def test_an_ungraded_execution_is_excluded_rather_than_scored_as_exact() -> None:
    """A prediction with no observation is unverified, not correct."""
    history = ExecutionHistory()
    history.record(executed(predicted=Prediction(entities=4, users=0)))
    assert history.estimation_error().samples == 0


# --- the published report -----------------------------------------------------


def test_the_report_publishes_failures_alongside_the_success_rate() -> None:
    history = ExecutionHistory()
    history.record(executed(Disposition.RESOLVED))
    history.record(executed(Disposition.ROLLED_BACK))
    history.record(executed(Disposition.ROLLBACK_FAILED))

    summary = report(history).summary()
    assert summary["executions"] == 3
    assert summary["resolved"] == 1
    assert summary["rolled_back"] == 1
    assert summary["escalated"] == 1
    assert summary["success_rate"] == 0.3333


def test_an_empty_report_does_not_claim_a_perfect_success_rate() -> None:
    assert report(ExecutionHistory()).success_rate == 0.0


def test_the_report_carries_the_systems_own_estimation_error() -> None:
    """The system publishing a metric about how wrong it is, rather than only
    metrics about how well it did."""
    history = ExecutionHistory()
    history.record(
        executed(predicted=Prediction(entities=1, users=0), observed=Prediction(entities=7, users=0))
    )
    assert report(history).summary()["estimation"] == EstimationError(
        samples=1,
        underestimates=1,
        worst_underestimate=6,
        total_signed_entities=6,
    ).summary()
