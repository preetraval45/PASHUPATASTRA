"""Approval records and the fatigue measurement.

The point of this module is to be uncomfortable, so most of these tests are about
refusing to produce a reassuring number: not collapsing two signals into one, not
returning `False` when the honest answer is "not enough evidence", and not
leading a summary with the flattering figure.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pashupatastra.approvals import (
    ApprovalLog,
    Decision,
    DELIBERATION_FLOOR_SECONDS,
)
from pashupatastra.dharma import Tier, Verdict

NOW = datetime(2026, 8, 18, 11, 0, 0).astimezone()


def a_verdict(action_id: str = "rollback_deployment", tier: Tier = Tier.APPROVAL) -> Verdict:
    return Verdict(
        action_id=action_id,
        incident_ref="INC-1",
        base_risk=45,
        adjustments=[],
        effective_risk=45,
        tier=tier,
        required_approvers=["sre-oncall"],
        expires_at=NOW + timedelta(minutes=15),
    )


def a_log(
    decisions: list[tuple[Decision, float, str]],
) -> ApprovalLog:
    """Build a log from (decision, seconds_taken, approver) triples."""
    log = ApprovalLog()
    for decision, seconds, approver in decisions:
        request = log.present(a_verdict(), at=NOW)
        log.resolve(request, decision, at=NOW + timedelta(seconds=seconds), approver=approver)
    return log


# --- one request --------------------------------------------------------------


def test_a_decision_records_who_and_how_long() -> None:
    log = ApprovalLog()
    request = log.present(a_verdict(), at=NOW)
    log.resolve(request, Decision.APPROVED, at=NOW + timedelta(seconds=42), approver="alice")

    assert request.approver == "alice"
    assert request.seconds_to_decide == 42
    assert not request.pending


def test_timing_starts_at_presentation_not_at_verdict_issuance() -> None:
    """The gap between Dharma deciding and an operator seeing the request is
    queueing, not deliberation. Charging it to the human flatters the number."""
    log = ApprovalLog()
    verdict = a_verdict()
    # Presented ten minutes after the verdict was issued.
    request = log.present(verdict, at=NOW + timedelta(minutes=10))
    log.resolve(request, Decision.APPROVED, at=NOW + timedelta(minutes=10, seconds=30),
                approver="alice")

    assert request.seconds_to_decide == 30, "the queueing time is not counted as thinking"


def test_a_second_decision_on_one_request_is_refused() -> None:
    """Two humans acting on one approval, or a replay. Silently overwriting would
    erase who actually decided."""
    log = ApprovalLog()
    request = log.present(a_verdict(), at=NOW)
    log.resolve(request, Decision.APPROVED, at=NOW, approver="alice")

    with pytest.raises(ValueError, match="already approved"):
        log.resolve(request, Decision.DENIED, at=NOW, approver="bob")


def test_denial_is_a_first_class_outcome() -> None:
    """A system that treats denial as a failure path teaches operators that
    saying no is the difficult option."""
    log = ApprovalLog()
    request = log.present(a_verdict(), at=NOW)
    log.resolve(request, Decision.DENIED, at=NOW + timedelta(seconds=60),
                approver="alice", reason="blast radius too wide during business hours")

    assert request.decision is Decision.DENIED
    assert "blast radius" in request.reason
    assert request in log.fatigue().decided, "denials count as decisions"


# --- expiry -------------------------------------------------------------------


def test_an_unanswered_request_expires_visibly() -> None:
    """`is_executable` already refuses a stale verdict, but an operator looking
    at a queue needs to see the window closed â€” not click a button that quietly
    does nothing."""
    log = ApprovalLog()
    verdict = a_verdict()
    request = log.present(verdict, at=NOW)

    expired = log.expire_stale(NOW + timedelta(minutes=20))
    assert expired == 1
    assert request.decision is Decision.EXPIRED


def test_expiry_does_not_touch_an_answered_request() -> None:
    log = ApprovalLog()
    verdict = a_verdict()
    request = log.present(verdict, at=NOW)
    log.resolve(request, Decision.APPROVED, at=NOW, approver="alice")

    assert log.expire_stale(NOW + timedelta(minutes=20)) == 0
    assert request.decision is Decision.APPROVED


def test_expired_requests_are_counted_apart_from_denials() -> None:
    """An unanswered request means the routing or the load is wrong â€” a different
    problem from a considered no."""
    log = ApprovalLog()
    verdict = a_verdict()
    log.present(verdict, at=NOW)
    log.expire_stale(NOW + timedelta(minutes=20))

    fatigue = log.fatigue()
    assert fatigue.expired == 1
    assert fatigue.decided == [], "an expiry is not a decision"


# --- the signal, and its halves ----------------------------------------------


def test_a_fast_decision_is_flagged_by_elapsed_time_only() -> None:
    """The system cannot see attention, only elapsed time â€” and the name says so."""
    log = a_log([(Decision.APPROVED, 2.0, "alice")])
    assert log.fatigue().requests[0].too_fast_to_have_read
    assert not a_log([(Decision.APPROVED, 60.0, "alice")]).fatigue().requests[0].too_fast_to_have_read


def test_a_high_approval_rate_alone_is_not_damning() -> None:
    """A well-calibrated system that only escalates when it should produces one.
    Humans agreeing is the system working."""
    log = a_log([(Decision.APPROVED, 120.0, "alice")] * 12)
    fatigue = log.fatigue()

    assert fatigue.approval_rate == 1.0
    assert fatigue.looks_decorative is False, "deliberated approvals are not decorative"


def test_fast_decisions_alone_are_not_damning() -> None:
    """An approver watching the incident may have decided before being asked."""
    log = a_log(
        [(Decision.APPROVED, 2.0, "alice")] * 6 + [(Decision.DENIED, 2.0, "alice")] * 6
    )
    fatigue = log.fatigue()

    assert fatigue.fast_decision_rate == 1.0
    assert fatigue.looks_decorative is False, "half were refused â€” someone is deciding"


def test_the_combination_is_what_indicates_a_formality() -> None:
    """Almost everything approved, almost instantly."""
    log = a_log([(Decision.APPROVED, 2.0, "alice")] * 12)
    assert log.fatigue().looks_decorative is True


def test_a_small_sample_returns_none_not_a_reassuring_false() -> None:
    """"Not enough evidence" and "no problem" are different claims, and only one
    of them should let someone stop worrying."""
    log = a_log([(Decision.APPROVED, 1.0, "alice")] * 3)
    assert log.fatigue().looks_decorative is None


def test_the_summary_leads_with_the_uncomfortable_number() -> None:
    """A summary that opens with "approval rate 98%" reads as a system running
    smoothly. The same data, led differently, prompts the right question."""
    keys = list(a_log([(Decision.APPROVED, 1.0, "alice")]).fatigue().summary())
    assert keys[0] == "looks_decorative"
    assert keys.index("fast_decision_rate") < keys.index("approval_rate")


def test_the_floor_is_documented_and_generous() -> None:
    """Set too low, the metric under-reports â€” the safer direction for a number
    whose job is to be uncomfortable."""
    assert DELIBERATION_FLOOR_SECONDS >= 5.0


# --- per-approver -------------------------------------------------------------


def test_one_rushed_approver_is_visible_behind_a_healthy_average() -> None:
    """A team where one person waves everything through is a different problem
    from a uniformly rushed team, and the aggregate hides which one you have."""
    log = a_log(
        [(Decision.APPROVED, 1.0, "rusher")] * 5
        + [(Decision.APPROVED, 180.0, "careful")] * 5
    )
    people = log.fatigue().by_approver()

    assert people["rusher"]["fast_decisions"] == 5
    assert people["careful"]["fast_decisions"] == 0
    assert people["rusher"]["median_seconds"] < people["careful"]["median_seconds"]


def test_the_aggregate_median_can_look_acceptable_while_one_person_does_not() -> None:
    log = a_log(
        [(Decision.APPROVED, 1.0, "rusher")] * 5
        + [(Decision.APPROVED, 300.0, "careful")] * 5
    )
    fatigue = log.fatigue()

    # The median sits between the two groups and flatters the rusher.
    assert fatigue.median_seconds_to_decide is not None
    assert fatigue.by_approver()["rusher"]["median_seconds"] == 1.0


# --- empty state --------------------------------------------------------------


def test_an_empty_log_reports_nothing_rather_than_zero_percent() -> None:
    fatigue = ApprovalLog().fatigue()
    assert fatigue.median_seconds_to_decide is None
    assert fatigue.looks_decorative is None


def test_a_pending_request_is_neither_approved_nor_denied() -> None:
    log = ApprovalLog()
    log.present(a_verdict(), at=NOW)
    fatigue = log.fatigue()

    assert fatigue.pending == 1
    assert fatigue.decided == []
    assert fatigue.approval_rate == 0.0


