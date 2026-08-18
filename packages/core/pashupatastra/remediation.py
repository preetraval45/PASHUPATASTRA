"""The guarded remediation loop: act, verify, roll back, escalate.

The registry already refuses to accept an action with no rollback. That guard is
structural but it is only a *declaration* — it proves a rollback ID was written
down, not that the rollback works. This module is where the declaration becomes a
runtime property, because a rollback that has never executed is a rollback you do
not have.

The loop is deliberately short and has no cycles:

    execute → verify → (pass)  → RESOLVED
                     → (fail)  → roll back → verify → (pass) → ROLLED_BACK
                                                     → (fail) → ROLLBACK_FAILED

**There is no retry of the original action.** An action that ran and did not
achieve its post-state has already changed the system; running it again changes
it further while the diagnosis is in doubt. The correct response to "that did not
work" is to undo it and hand over, not to try harder.

**`ROLLBACK_FAILED` is the worst outcome in the system and is modelled as a
first-class state**, not an exception. The system has acted, the action did not
work, and the undo did not work either — so the environment is in a state nobody
designed and nobody is watching. That has to page a human with everything needed
to reconstruct what happened; a stack trace in a log is not that.

**Verification is observational.** It compares observed state to the post-state
the action declared *before* it ran, and a missing observation grades as failure —
never as success. "We could not tell" and "it worked" are different answers, and
only one of them should close an incident.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .dharma import ActionSpec, Verdict
from .incidents import VerificationCheck


class Disposition(StrEnum):
    """How a remediation ended. Ordered best to worst."""

    RESOLVED = "resolved"
    """Acted, and verification confirmed the expected post-state."""

    ROLLED_BACK = "rolled_back"
    """Acted, verification failed, the undo worked and was itself verified.

    A *success* outcome for the safety machinery even though the incident is
    unresolved: the system tried something, it did not work, and it put the
    environment back. Counting this as a failure would create pressure to skip
    the rollback."""

    ESCALATED = "escalated"
    """Handed to a human without acting, or after acting safely. Also a success
    outcome — the benchmark measures false remediation precisely so that guessing
    is never rewarded over handing off."""

    ROLLBACK_FAILED = "rollback_failed"
    """The worst case. Acted, it did not work, and the undo did not work either.
    The environment is in a state nobody designed."""

    BLOCKED = "blocked"
    """Policy refused. Nothing was attempted."""

    @property
    def needs_human(self) -> bool:
        return self in (
            Disposition.ESCALATED,
            Disposition.ROLLBACK_FAILED,
            Disposition.BLOCKED,
        )

    @property
    def environment_uncertain(self) -> bool:
        """Whether the system no longer knows what state it left behind.

        Only `ROLLBACK_FAILED` qualifies. It is separated from `needs_human`
        because the urgency is different: an escalation can wait for the next
        working hour, an uncertain environment cannot.
        """
        return self is Disposition.ROLLBACK_FAILED


@dataclass
class Attempt:
    """One execution — the original action or its rollback."""

    action_id: str
    started_at: datetime
    finished_at: datetime | None = None
    executed: bool = False
    """Whether the executor ran at all. False means it was never attempted."""

    succeeded: bool | None = None
    """Whether the executor reported success. Distinct from whether it *worked*
    — that is what verification answers."""

    checks: list[VerificationCheck] = field(default_factory=list)
    output: str = ""
    error: str | None = None

    @property
    def verified(self) -> bool:
        """True only when every declared check was observed and passed.

        A check with `passed is None` was never observed, and grades as failure.
        An empty check list also grades as failure for anything that declared a
        post-state: claiming success with no evidence is the thing this module
        exists to prevent.
        """
        if not self.checks:
            return False
        return all(check.passed is True for check in self.checks)

    @property
    def unobserved(self) -> list[str]:
        return [check.name for check in self.checks if check.passed is None]


@dataclass
class Remediation:
    """The full record of one attempt to fix something.

    Everything an operator or the audit trail needs to reconstruct the decision,
    including the attempts that failed — especially those.
    """

    action_id: str
    disposition: Disposition
    attempt: Attempt | None = None
    rollback: Attempt | None = None
    reason: str = ""

    @property
    def acted(self) -> bool:
        return self.attempt is not None and self.attempt.executed

    def page(self) -> str | None:
        """What to put in front of a human, or `None` if nothing is needed.

        Written as prose rather than a status code because the reader is a person
        who has just been woken up, and the first thing they need is what state
        the system is in — not which enum member was returned.
        """
        match self.disposition:
            case Disposition.ROLLBACK_FAILED:
                unobserved = self.rollback.unobserved if self.rollback else []
                detail = (
                    f" Unverified checks: {', '.join(unobserved)}." if unobserved else ""
                )
                return (
                    f"URGENT: {self.action_id} did not achieve its expected state and the "
                    f"rollback ({self.rollback.action_id if self.rollback else 'none'}) "
                    f"also failed. The environment is in an unintended state and no further "
                    f"automated action will be taken.{detail} Reason: {self.reason}"
                )
            case Disposition.ESCALATED:
                return f"Escalated without resolving: {self.reason}"
            case Disposition.BLOCKED:
                return f"Policy refused {self.action_id}: {self.reason}"
            case Disposition.ROLLED_BACK:
                return (
                    f"{self.action_id} did not work and was rolled back successfully. "
                    f"The incident is still open. Reason: {self.reason}"
                )
            case _:
                return None


# --- the collaborators, as protocols ------------------------------------------
#
# Callables rather than classes: this module needs to run in tests without a
# cluster, and the seam has to be narrow enough that a fake is obviously
# equivalent to the real thing.

Runner = Callable[[ActionSpec, dict[str, str]], str]
"""Executes an action. Raises on failure."""

Observer = Callable[[ActionSpec, dict[str, str]], list[VerificationCheck]]
"""Observes the world and grades the action's declared post-state."""

Capture = Callable[[ActionSpec, dict[str, str]], dict[str, str]]
"""Snapshots the state a rollback would need in order to restore it.

Called **before** the action runs, because afterwards the information is gone.
Returns the parameters the rollback should be invoked with — `{"replicas": "2"}`
before scaling to 5, so the undo scales back to 2 rather than to 5 again.

This exists because live testing found the loop passing the *original* params to
the rollback, which for `scale_service` meant "undoing" a scale-to-5 by scaling
to 5. The rollback ran, reported success, and changed nothing — the most
dangerous shape of bug available here, since every layer above would have
recorded a successful undo.
"""


class Remediator:
    """Runs the guarded loop for one action.

    Takes a runner and an observer rather than reaching for connectors itself, so
    the sequencing logic — which is the part that matters and the part that is
    hard to get right — is testable without any infrastructure at all.
    """

    def __init__(
        self,
        runner: Runner,
        observer: Observer,
        rollback_of: Callable[[str], ActionSpec | None],
        capture: Capture | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.runner = runner
        self.observer = observer
        self.rollback_of = rollback_of
        self.capture = capture
        self._now = clock or (lambda: datetime.now().astimezone())

    def remediate(
        self,
        action: ActionSpec,
        verdict: Verdict | None,
        params: dict[str, str] | None = None,
    ) -> Remediation:
        """Execute, verify, and undo if it did not work."""
        params = params or {}

        if verdict is None:
            return Remediation(
                action_id=action.id,
                disposition=Disposition.BLOCKED,
                reason="no policy verdict — nothing was attempted",
            )

        # Snapshot before acting: afterwards the prior state is gone, and a
        # rollback with no idea what to restore is a rollback in name only.
        restore_to: dict[str, str] | None = None
        if self.capture is not None:
            try:
                restore_to = self.capture(action, params)
            except Exception as error:  # noqa: BLE001
                # Refuse to act rather than act without an undo. This is the
                # conservative direction and the cheap one: not acting costs an
                # escalation, acting blind costs an unrecoverable change.
                return Remediation(
                    action_id=action.id,
                    disposition=Disposition.ESCALATED,
                    reason=(
                        f"could not capture the state a rollback would restore "
                        f"({type(error).__name__}: {error}); refusing to act without an undo"
                    ),
                )

        attempt = self._run(action, params)

        if attempt.error is not None:
            # The executor itself failed, so the action may or may not have taken
            # effect. Rolling back is the safe response to that ambiguity: a
            # rollback on a system that was never changed is usually a no-op,
            # while skipping it on a system that *was* changed leaves it altered
            # with nobody aware.
            return self._undo(
                action,
                attempt,
                params,
                restore_to,
                reason=f"execution failed: {attempt.error}",
            )

        if attempt.verified:
            return Remediation(
                action_id=action.id,
                disposition=Disposition.RESOLVED,
                attempt=attempt,
                reason="expected post-state observed",
            )

        unobserved = attempt.unobserved
        reason = (
            f"could not observe: {', '.join(unobserved)}"
            if unobserved
            else "expected post-state not reached"
        )
        return self._undo(action, attempt, params, restore_to, reason=reason)

    # -- internals ------------------------------------------------------------

    def _run(self, action: ActionSpec, params: dict[str, str]) -> Attempt:
        attempt = Attempt(action_id=action.id, started_at=self._now())
        try:
            attempt.output = self.runner(action, params)
            attempt.executed = True
            attempt.succeeded = True
        except Exception as error:  # noqa: BLE001 — failure is an outcome, not a crash
            attempt.executed = True
            attempt.succeeded = False
            attempt.error = f"{type(error).__name__}: {error}"
            attempt.finished_at = self._now()
            return attempt

        # Verification only happens if the executor claimed success. Grading the
        # post-state of an action that errored would conflate "it did not run"
        # with "it ran and did not work".
        try:
            attempt.checks = self.observer(action, params)
        except Exception as error:  # noqa: BLE001
            # An observer that cannot see grades as failure, never as success.
            attempt.checks = [
                VerificationCheck(name="observation", expected="observable", observed=None)
            ]
            attempt.error = None
            attempt.output += f" [observation failed: {type(error).__name__}: {error}]"

        attempt.finished_at = self._now()
        return attempt

    def _undo(
        self,
        action: ActionSpec,
        attempt: Attempt,
        params: dict[str, str],
        restore_to: dict[str, str] | None,
        reason: str,
    ) -> Remediation:
        """Roll back, and handle the case where the rollback fails too."""
        rollback_spec = self.rollback_of(action.id)

        if rollback_spec is not None and rollback_spec.id == action.id and not restore_to:
            # A self-rollback with nothing to restore is not an undo, it is the
            # same action again. Found on a live cluster: `restart_service`
            # declares itself as its rollback, so the loop restarted a deployment
            # twice in one second and Kubernetes refused the second — which
            # surfaced as ROLLBACK_FAILED, a page for a state that was never
            # actually broken.
            #
            # The registry's guard is satisfied by *declaring* a rollback ID; it
            # cannot tell that restarting again undoes nothing. Escalating is the
            # honest outcome: there is no undo for this action, and pretending
            # otherwise is worse than admitting it.
            return Remediation(
                action_id=action.id,
                disposition=Disposition.ESCALATED,
                attempt=attempt,
                reason=(
                    f"{reason}; {action.id} declares itself as its own rollback and no prior "
                    "state was captured, so repeating it would not undo anything"
                ),
            )

        if rollback_spec is None:
            # Nothing to undo with. The registry forbids this above risk 0, so
            # reaching here means either a risk-0 action (nothing to undo) or a
            # declared-irreversible one — both of which are a human's problem now.
            return Remediation(
                action_id=action.id,
                disposition=Disposition.ESCALATED,
                attempt=attempt,
                reason=f"{reason}; no rollback is declared for this action",
            )

        # The rollback runs with the *captured prior state* where one exists,
        # not the original parameters. Undoing a scale-to-5 by scaling to 5 would
        # report success and change nothing — the most dangerous shape of bug
        # here, since every layer above would record a successful undo.
        rollback = self._run(rollback_spec, restore_to if restore_to else params)

        if rollback.error is not None:
            return Remediation(
                action_id=action.id,
                disposition=Disposition.ROLLBACK_FAILED,
                attempt=attempt,
                rollback=rollback,
                reason=f"{reason}; rollback errored: {rollback.error}",
            )

        if not rollback.verified:
            # The rollback ran without erroring but did not demonstrably restore
            # the prior state. Treated as failure rather than success: an
            # unverified undo is indistinguishable from no undo, and assuming it
            # worked is how the environment drifts silently.
            return Remediation(
                action_id=action.id,
                disposition=Disposition.ROLLBACK_FAILED,
                attempt=attempt,
                rollback=rollback,
                reason=f"{reason}; rollback ran but its effect could not be verified",
            )

        return Remediation(
            action_id=action.id,
            disposition=Disposition.ROLLED_BACK,
            attempt=attempt,
            rollback=rollback,
            reason=reason,
        )


# --- measurement --------------------------------------------------------------


@dataclass
class RemediationQuality:
    """Outcomes across many remediations, worst first."""

    rollback_failed: int = 0
    escalated: int = 0
    rolled_back: int = 0
    resolved: int = 0
    blocked: int = 0

    @property
    def total(self) -> int:
        return (
            self.rollback_failed
            + self.escalated
            + self.rolled_back
            + self.resolved
            + self.blocked
        )

    @property
    def uncertain_environment_rate(self) -> float:
        """The number that decides whether autonomy is safe to widen.

        Not "success rate": a system that resolves 95% of incidents and leaves
        the environment in an unknown state for the other 5% is not 95% good, it
        is unfit. This is the metric to look at first, which is why it is the
        first field.
        """
        return round(self.rollback_failed / self.total, 4) if self.total else 0.0

    @property
    def autonomous_resolution_rate(self) -> float:
        return round(self.resolved / self.total, 4) if self.total else 0.0

    def summary(self) -> dict[str, object]:
        """Failures before successes, per the roadmap's reporting rule."""
        return {
            "rollback_failed": self.rollback_failed,
            "uncertain_environment_rate": self.uncertain_environment_rate,
            "escalated": self.escalated,
            "rolled_back": self.rolled_back,
            "blocked": self.blocked,
            "resolved": self.resolved,
            "autonomous_resolution_rate": self.autonomous_resolution_rate,
            "total": self.total,
        }


def score_remediations(remediations: list[Remediation]) -> RemediationQuality:
    quality = RemediationQuality()
    for remediation in remediations:
        match remediation.disposition:
            case Disposition.RESOLVED:
                quality.resolved += 1
            case Disposition.ROLLED_BACK:
                quality.rolled_back += 1
            case Disposition.ESCALATED:
                quality.escalated += 1
            case Disposition.ROLLBACK_FAILED:
                quality.rollback_failed += 1
            case Disposition.BLOCKED:
                quality.blocked += 1
    return quality
