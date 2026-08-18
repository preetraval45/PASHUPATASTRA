"""Approval records, and the measurement that says whether they mean anything.

A policy layer that routes risky actions to a human is only a safety mechanism if
the human is actually deciding. If every request is approved in two seconds, the
tier system has become a speed bump with an audit trail: the same actions happen,
they just acquire a name attached to them. That is arguably **worse than no
approval step**, because it manufactures accountability — an operator's name sits
on a decision they did not really make, and everyone downstream reads the
approval as evidence the action was considered.

So this module measures the approval step itself, and reports the unflattering
number first.

**The signal is a combination, not any single figure.** Read alone, each is
innocent:

* A **high approval rate** is what a well-calibrated system produces. If it only
  escalates when it genuinely should, humans agreeing most of the time is the
  system working, not failing.
* A **fast decision** may be entirely informed. The approver was probably
  watching the incident already and may have decided before the request arrived.

It is *high approval rate together with consistently near-instant decisions*
that indicates nobody is reading. Neither half convicts on its own, and this
module deliberately refuses to collapse them into one score.

**"Too fast to have read" is a signal, not a verdict.** The wording matters and
is kept throughout: the system cannot see attention, only elapsed time. It can
say a decision took two seconds; it cannot say it was careless. Presenting an
inference as an observation here would be the same error the reasoning layer is
built to avoid.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .dharma import Tier, Verdict

DELIBERATION_FLOOR_SECONDS = 10.0
"""Below this, a decision is unlikely to have involved reading the request.

The approval surface presents the risk arithmetic, the blast radius, the expected
post-state and the rollback. Ten seconds is not enough to take all four in from a
standing start — it is roughly the time to find the button.

Chosen as a defensible round number rather than derived, and deliberately
generous: the cost of setting it too low is under-reporting a real problem, which
is the safer direction for a metric whose whole job is to be uncomfortable.
"""


class Decision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    """A first-class outcome, not an error. A denial is the approval step doing
    its job, and a system that treats it as a failure path teaches operators that
    saying no is the difficult option."""

    EXPIRED = "expired"
    """Nobody decided in time. Also not an error: an unanswered request is a
    signal that the routing is wrong or the operator is overloaded, and folding
    it into denials would hide that."""


@dataclass
class ApprovalRequest:
    """One request put in front of a human, and what came back."""

    action_id: str
    incident_ref: str | None
    tier: Tier
    effective_risk: int
    presented_at: datetime
    expires_at: datetime | None = None
    """Copied from the verdict at presentation, so the request carries its own
    deadline. Pairing requests with verdicts externally made the caller hold the
    association and get it wrong."""

    decision: Decision | None = None
    decided_at: datetime | None = None
    approver: str | None = None
    reason: str | None = None

    @property
    def seconds_to_decide(self) -> float | None:
        if self.decided_at is None:
            return None
        return (self.decided_at - self.presented_at).total_seconds()

    @property
    def pending(self) -> bool:
        return self.decision is None

    @property
    def too_fast_to_have_read(self) -> bool:
        """Elapsed time below the deliberation floor.

        Named for what it measures — elapsed time — rather than for what it might
        imply. The system cannot see attention.
        """
        seconds = self.seconds_to_decide
        return seconds is not None and seconds < DELIBERATION_FLOOR_SECONDS

    def resolve(
        self,
        decision: Decision,
        at: datetime,
        approver: str | None = None,
        reason: str | None = None,
    ) -> ApprovalRequest:
        """Record the outcome. Idempotent-hostile on purpose.

        A second decision on the same request is a bug — two humans acting on one
        approval, or a replay — and silently overwriting the first would erase who
        actually decided.
        """
        if self.decision is not None:
            raise ValueError(
                f"{self.action_id} was already {self.decision.value} "
                f"by {self.approver or 'unknown'}; a second decision would erase the first"
            )
        self.decision = decision
        self.decided_at = at
        self.approver = approver
        self.reason = reason
        return self


@dataclass
class ApprovalFatigue:
    """How the approval step is behaving, across many requests."""

    requests: list[ApprovalRequest] = field(default_factory=list)

    # -- the components, kept separate ---------------------------------------

    @property
    def decided(self) -> list[ApprovalRequest]:
        return [r for r in self.requests if not r.pending and r.decision is not Decision.EXPIRED]

    @property
    def approval_rate(self) -> float:
        """Innocent on its own — a well-calibrated system produces a high one."""
        if not self.decided:
            return 0.0
        approved = sum(1 for r in self.decided if r.decision is Decision.APPROVED)
        return round(approved / len(self.decided), 4)

    @property
    def median_seconds_to_decide(self) -> float | None:
        times = [r.seconds_to_decide for r in self.decided if r.seconds_to_decide is not None]
        return round(statistics.median(times), 2) if times else None

    @property
    def fast_decision_rate(self) -> float:
        """Share of decisions made below the deliberation floor."""
        if not self.decided:
            return 0.0
        fast = sum(1 for r in self.decided if r.too_fast_to_have_read)
        return round(fast / len(self.decided), 4)

    @property
    def expired(self) -> int:
        """Requests nobody answered. Counted separately from denials, because an
        unanswered request means the routing or the load is wrong — a different
        problem from a considered no."""
        return sum(1 for r in self.requests if r.decision is Decision.EXPIRED)

    @property
    def pending(self) -> int:
        return sum(1 for r in self.requests if r.pending)

    def by_approver(self) -> dict[str, dict[str, object]]:
        """Per-person breakdown.

        A team where one person approves everything instantly and everyone else
        deliberates is a different problem from a team that is uniformly rushed,
        and the aggregate hides which one you have.
        """
        people: dict[str, list[ApprovalRequest]] = {}
        for request in self.decided:
            if request.approver:
                people.setdefault(request.approver, []).append(request)

        return {
            approver: {
                "decisions": len(rs),
                "approval_rate": round(
                    sum(1 for r in rs if r.decision is Decision.APPROVED) / len(rs), 4
                ),
                "median_seconds": round(
                    statistics.median([r.seconds_to_decide or 0.0 for r in rs]), 2
                ),
                "fast_decisions": sum(1 for r in rs if r.too_fast_to_have_read),
            }
            for approver, rs in sorted(people.items())
        }

    # -- the combination ------------------------------------------------------

    @property
    def looks_decorative(self) -> bool | None:
        """Whether the approval step appears to be a formality.

        Requires **both** halves: almost everything approved, *and* most decisions
        made too fast to have read the request. Either alone is consistent with a
        system working properly.

        Returns `None` below a usable sample rather than a reassuring `False` —
        "not enough evidence" and "no problem" are different claims, and only one
        of them should let someone stop worrying.
        """
        if len(self.decided) < 10:
            return None
        return self.approval_rate >= 0.95 and self.fast_decision_rate >= 0.5

    def summary(self) -> dict[str, object]:
        """The uncomfortable numbers first.

        A summary that leads with "approval rate 98%" reads as a system running
        smoothly. Leading with the fast-decision rate makes the reader ask the
        right question about the same data.
        """
        return {
            "looks_decorative": self.looks_decorative,
            "fast_decision_rate": self.fast_decision_rate,
            "median_seconds_to_decide": self.median_seconds_to_decide,
            "expired": self.expired,
            "pending": self.pending,
            "approval_rate": self.approval_rate,
            "decisions": len(self.decided),
        }


class ApprovalLog:
    """Records requests and their outcomes, and reports on the pattern."""

    def __init__(self) -> None:
        self._requests: list[ApprovalRequest] = []

    def present(self, verdict: Verdict, at: datetime) -> ApprovalRequest:
        """Record that a request was put in front of a human.

        Timed from presentation rather than from verdict issuance: the gap
        between Dharma deciding and an operator seeing the request is queueing,
        not deliberation, and charging it to the human would flatter the number.
        """
        request = ApprovalRequest(
            action_id=verdict.action_id,
            incident_ref=verdict.incident_ref,
            tier=verdict.tier,
            effective_risk=verdict.effective_risk,
            presented_at=at,
            expires_at=verdict.expires_at,
        )
        self._requests.append(request)
        return request

    def resolve(
        self,
        request: ApprovalRequest,
        decision: Decision,
        at: datetime,
        approver: str | None = None,
        reason: str | None = None,
    ) -> ApprovalRequest:
        return request.resolve(decision, at, approver, reason)

    def expire_stale(self, now: datetime) -> int:
        """Mark unanswered requests expired once their verdict has lapsed.

        A stale approval must visibly expire rather than silently work:
        `Verdict.is_executable` already refuses an expired one, but an operator
        looking at a queue needs to see that the window closed, not click a
        button that quietly does nothing.
        """
        expired = 0
        for request in self._requests:
            if not request.pending or request.expires_at is None:
                continue
            if now > request.expires_at:
                request.resolve(Decision.EXPIRED, now, reason="verdict expired unanswered")
                expired += 1
        return expired

    def fatigue(self) -> ApprovalFatigue:
        return ApprovalFatigue(requests=list(self._requests))

    def __len__(self) -> int:
        return len(self._requests)
