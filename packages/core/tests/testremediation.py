"""The guarded remediation loop.

The registry guard proves a rollback ID was *written down*. These tests are where
that becomes a runtime property, so the weight is on the paths that only happen
when something has already gone wrong — verification failing, the rollback
failing, and the observer being unable to see.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pashupatastra.dharma import ActionSpec, Tier, Verdict
from pashupatastra.incidents import VerificationCheck
from pashupatastra.registry import all_actions, get
from pashupatastra.remediation import (
    Disposition,
    Remediation,
    Remediator,
    score_remediations,
)

NOW = datetime(2026, 8, 18, 9, 0, 0).astimezone()


def an_action(
    action_id: str = "rollback_deployment", rollback: str | None = "redeploy_version"
) -> ActionSpec:
    """A genuine rollback pair by default.

    Deliberately *not* `restart_service`, whose declared rollback is itself — a
    self-rollback with nothing to restore now escalates rather than repeating the
    action, so using it as the default fixture would test the escalation path
    everywhere instead of the rollback path.
    """
    return ActionSpec(
        id=action_id,
        description="test",
        base_risk=10,
        expected_post_state={"health": "healthy"},
        rollback_action_id=rollback,
    )


def a_verdict() -> Verdict:
    return Verdict(
        action_id="restart_service",
        incident_ref="INC-1",
        base_risk=10,
        adjustments=[],
        effective_risk=10,
        tier=Tier.AUTONOMOUS,
        required_approvers=[],
        expires_at=NOW + timedelta(minutes=15),
    )


def passing_check() -> list[VerificationCheck]:
    return [VerificationCheck(name="health", expected="healthy", observed="healthy", passed=True)]


def failing_check() -> list[VerificationCheck]:
    return [VerificationCheck(name="health", expected="healthy", observed="crashloop", passed=False)]


def unobserved_check() -> list[VerificationCheck]:
    return [VerificationCheck(name="health", expected="healthy", observed=None, passed=None)]


def a_remediator(
    run_results: list[str | Exception],
    observations: list[list[VerificationCheck]],
) -> tuple[Remediator, list[str]]:
    """A remediator whose runner and observer are scripted per call."""
    calls: list[str] = []
    runs = iter(run_results)
    observes = iter(observations)

    def runner(action: ActionSpec, params: dict[str, str]) -> str:
        calls.append(action.id)
        result = next(runs)
        if isinstance(result, Exception):
            raise result
        return result

    def observer(action: ActionSpec, params: dict[str, str]) -> list[VerificationCheck]:
        return next(observes)

    return (
        Remediator(
            runner,
            observer,
            rollback_of=lambda _id: an_action("redeploy_version", rollback="rollback_deployment"),
            clock=lambda: NOW,
        ),
        calls,
    )


# --- the happy path -----------------------------------------------------------


def test_a_verified_action_resolves() -> None:
    remediator, calls = a_remediator(["ok"], [passing_check()])
    result = remediator.remediate(an_action(), a_verdict())

    assert result.disposition is Disposition.RESOLVED
    assert calls == ["rollback_deployment"], "no rollback when the action worked"
    assert result.page() is None, "nothing to wake anyone for"


# --- verification failure -----------------------------------------------------


def test_an_unverified_action_is_rolled_back() -> None:
    """The action ran without erroring and did not achieve its post-state."""
    remediator, calls = a_remediator(["ok", "undone"], [failing_check(), passing_check()])
    result = remediator.remediate(an_action(), a_verdict())

    assert result.disposition is Disposition.ROLLED_BACK
    assert len(calls) == 2, "the rollback ran"
    assert "still open" in result.page()


def test_the_original_action_is_never_retried() -> None:
    """An action that ran and did not work has already changed the system.
    Running it again changes it further while the diagnosis is in doubt."""
    remediator, calls = a_remediator(["ok", "undone"], [failing_check(), passing_check()])
    remediator.remediate(an_action(), a_verdict())
    assert calls == ["rollback_deployment", "redeploy_version"], (
        "once to act, once to undo — never a retry of the original"
    )


def test_an_unobservable_post_state_grades_as_failure_not_success() -> None:
    """"We could not tell" and "it worked" are different answers, and only one of
    them should close an incident."""
    remediator, _ = a_remediator(["ok", "undone"], [unobserved_check(), passing_check()])
    result = remediator.remediate(an_action(), a_verdict())

    assert result.disposition is Disposition.ROLLED_BACK
    assert "could not observe" in result.reason


def test_no_checks_at_all_grades_as_failure() -> None:
    """Claiming success with no evidence is the thing this module prevents."""
    remediator, _ = a_remediator(["ok", "undone"], [[], passing_check()])
    result = remediator.remediate(an_action(), a_verdict())
    assert result.disposition is Disposition.ROLLED_BACK


def test_an_observer_that_cannot_see_does_not_pass_the_action() -> None:
    """An exception while observing must not read as a clean verification."""

    def runner(action: ActionSpec, params: dict[str, str]) -> str:
        return "ok"

    seen = {"count": 0}

    def observer(action: ActionSpec, params: dict[str, str]) -> list[VerificationCheck]:
        seen["count"] += 1
        if seen["count"] == 1:
            raise ConnectionError("metrics unreachable")
        return passing_check()

    remediator = Remediator(
        runner,
        observer,
        rollback_of=lambda _id: an_action("redeploy_version", rollback="rollback_deployment"),
        clock=lambda: NOW,
    )
    result = remediator.remediate(an_action(), a_verdict())
    assert result.disposition is Disposition.ROLLED_BACK


# --- execution failure --------------------------------------------------------


def test_an_execution_error_still_triggers_a_rollback() -> None:
    """The safe response to ambiguity. A rollback on a system that was never
    changed is usually a no-op; skipping it on a system that *was* changed leaves
    it altered with nobody aware."""
    remediator, calls = a_remediator(
        [RuntimeError("connection reset"), "undone"], [passing_check()]
    )
    result = remediator.remediate(an_action(), a_verdict())

    assert result.disposition is Disposition.ROLLED_BACK
    assert len(calls) == 2
    assert "execution failed" in result.reason


# --- the worst case -----------------------------------------------------------


def test_a_failing_rollback_is_a_first_class_state_not_an_exception() -> None:
    """The system acted, it did not work, and the undo did not work either. The
    environment is in a state nobody designed."""
    remediator, _ = a_remediator(
        ["ok", RuntimeError("api server unreachable")], [failing_check()]
    )
    result = remediator.remediate(an_action(), a_verdict())

    assert result.disposition is Disposition.ROLLBACK_FAILED
    assert result.disposition.environment_uncertain
    assert result.disposition.needs_human


def test_an_unverified_rollback_counts_as_a_failed_rollback() -> None:
    """An undo that ran but cannot be shown to have worked is indistinguishable
    from no undo. Assuming it worked is how the environment drifts silently."""
    remediator, _ = a_remediator(["ok", "undone"], [failing_check(), failing_check()])
    result = remediator.remediate(an_action(), a_verdict())

    assert result.disposition is Disposition.ROLLBACK_FAILED
    assert "could not be verified" in result.reason


def test_the_worst_case_pages_a_human_in_prose() -> None:
    """The reader has just been woken up. The first thing they need is what state
    the system is in, not which enum member was returned."""
    remediator, _ = a_remediator(["ok", RuntimeError("boom")], [failing_check()])
    page = remediator.remediate(an_action(), a_verdict()).page()

    assert page.startswith("URGENT")
    assert "unintended state" in page
    assert "no further" in page, "it must say that automation has stopped"


def test_the_loop_terminates_and_never_retries_the_rollback() -> None:
    """Bounded attempts, then a human. A retry loop here would compound damage
    on a system already in an unknown state."""
    remediator, calls = a_remediator(
        ["ok", RuntimeError("boom")], [failing_check()]
    )
    remediator.remediate(an_action(), a_verdict())
    assert len(calls) == 2, "one action, one rollback, no more"


# --- prior state, found by running against a real cluster --------------------


def test_the_rollback_restores_captured_state_not_the_original_params() -> None:
    """Undoing a scale-to-5 by scaling to 5 reports success and changes nothing.

    The most dangerous shape of bug available here: every layer above records a
    successful undo. Found on a live cluster, not by the mocked tests — a fake
    executor cannot tell the two calls apart.
    """
    seen: list[dict[str, str]] = []

    def runner(action: ActionSpec, params: dict[str, str]) -> str:
        seen.append(dict(params))
        return "ok"

    observations = iter([failing_check(), passing_check()])
    remediator = Remediator(
        runner,
        lambda a, p: next(observations),
        rollback_of=lambda _id: an_action("scale_service", rollback="scale_service"),
        capture=lambda a, p: {"replicas": "2"},
    )
    result = remediator.remediate(
        an_action("scale_service", rollback="scale_service"), a_verdict(), {"replicas": "5"}
    )

    assert result.disposition is Disposition.ROLLED_BACK
    assert seen[0]["replicas"] == "5", "the action scaled up"
    assert seen[1]["replicas"] == "2", "the rollback restored the prior count"


def test_a_self_rollback_with_nothing_to_restore_escalates() -> None:
    """`restart_service` declares itself as its rollback. Restarting again does
    not undo a restart — it repeats it.

    Live testing surfaced this as Kubernetes refusing two restarts in one second,
    reported as ROLLBACK_FAILED — a page for a state that was never broken. The
    registry cannot catch it: its guard is satisfied by declaring an ID.
    """
    remediator, calls = a_remediator(["ok"], [failing_check()])
    remediator.rollback_of = lambda _id: an_action("restart_service", rollback="restart_service")
    result = remediator.remediate(
        an_action("restart_service", rollback="restart_service"), a_verdict()
    )

    assert result.disposition is Disposition.ESCALATED
    assert "would not undo anything" in result.reason
    assert len(calls) == 1, "the pointless second restart was never attempted"


def test_a_self_rollback_is_allowed_when_prior_state_was_captured() -> None:
    """`scale_service` is legitimately its own inverse — with different params."""
    remediator, calls = a_remediator(["ok", "restored"], [failing_check(), passing_check()])
    remediator.capture = lambda a, p: {"replicas": "2"}
    result = remediator.remediate(
        an_action("scale_service", rollback="scale_service"), a_verdict(), {"replicas": "9"}
    )

    assert result.disposition is Disposition.ROLLED_BACK
    assert len(calls) == 2


def test_refusing_to_act_when_prior_state_cannot_be_captured() -> None:
    """Not acting costs an escalation; acting blind costs an unrecoverable
    change. The cheap direction is not acting."""

    def capture(action: ActionSpec, params: dict[str, str]) -> dict[str, str]:
        raise ConnectionError("cluster unreachable")

    remediator, calls = a_remediator(["ok"], [passing_check()])
    remediator.capture = capture
    result = remediator.remediate(an_action(), a_verdict())

    assert result.disposition is Disposition.ESCALATED
    assert "refusing to act without an undo" in result.reason
    assert calls == [], "nothing was attempted"


# --- policy and irreversibility ----------------------------------------------


def test_no_verdict_means_nothing_is_attempted() -> None:
    remediator, calls = a_remediator([], [])
    result = remediator.remediate(an_action(), verdict=None)

    assert result.disposition is Disposition.BLOCKED
    assert calls == []
    assert not result.acted


def test_an_action_with_no_rollback_escalates_rather_than_guessing() -> None:
    remediator, calls = a_remediator(["ok"], [failing_check()])
    remediator.rollback_of = lambda _id: None
    result = remediator.remediate(an_action(rollback=None), a_verdict())

    assert result.disposition is Disposition.ESCALATED
    assert "no rollback is declared" in result.reason
    assert len(calls) == 1


# --- dispositions -------------------------------------------------------------


def test_rolling_back_successfully_is_a_success_outcome() -> None:
    """Counting it as a failure would create pressure to skip the rollback."""
    assert not Disposition.ROLLED_BACK.needs_human
    assert not Disposition.ROLLED_BACK.environment_uncertain


def test_escalation_needs_a_human_but_the_environment_is_known() -> None:
    """The urgency differs: an escalation can wait for working hours, an
    uncertain environment cannot."""
    assert Disposition.ESCALATED.needs_human
    assert not Disposition.ESCALATED.environment_uncertain


# --- the runtime rollback guarantee ------------------------------------------


def test_every_registered_action_with_a_distinct_rollback_can_actually_run_it() -> None:
    """The registry guard is compile-time; this is the runtime half.

    Walks the real registry, executes each action and forces its rollback, and
    asserts the rollback both resolves to a registered action and completes. A
    rollback ID pointing at nothing would pass the registry check and fail here —
    which is the whole point of having both.
    """
    executed: list[str] = []

    def runner(action: ActionSpec, params: dict[str, str]) -> str:
        executed.append(action.id)
        return "ok"

    def observer(action: ActionSpec, params: dict[str, str]) -> list[VerificationCheck]:
        # Fail the first observation so the rollback is forced, pass the second.
        return failing_check() if len(executed) == 1 else passing_check()

    checked = 0
    for action in all_actions():
        if action.rollback_action_id in (None, action.id):
            continue  # self-rollbacks are covered by the test below
        executed.clear()
        remediator = Remediator(
            runner, observer, rollback_of=lambda i: get(get(i).rollback_action_id or i)
        )
        result = remediator.remediate(action, a_verdict())

        assert result.disposition is Disposition.ROLLED_BACK, (
            f"{action.id}: rollback {action.rollback_action_id} did not complete"
        )
        assert executed == [action.id, action.rollback_action_id]
        checked += 1

    assert checked >= 3, "the walk must actually cover some actions"


def test_the_registry_still_contains_self_rollbacks_that_cannot_undo() -> None:
    """A finding, pinned rather than quietly fixed.

    `restart_service` and `modify_db_config` declare *themselves* as their
    rollback. That satisfies the registry — which only checks an ID was written
    down — while undoing nothing. `scale_service` is the legitimate case: it is
    genuinely its own inverse, but only with different parameters, which is why
    the loop now requires captured prior state before it will run a self-rollback.

    Left as a documented gap rather than silently repaired: deciding what the
    rollback of a restart *should* be is a policy question, and the registry's
    binary rollback-or-irreversible model does not currently express "low risk,
    self-healing, not undoable".
    """
    self_rollbacks = {
        action.id for action in all_actions() if action.rollback_action_id == action.id
    }
    assert self_rollbacks == {"restart_service", "scale_service", "modify_db_config"}


def test_the_registry_still_refuses_a_risky_action_with_no_rollback() -> None:
    """The compile-time half, asserted here so the pair is visible together."""
    from pashupatastra.registry import register

    with pytest.raises(ValueError, match="no rollback"):
        register(
            ActionSpec(
                id="dangerous_test_action",
                description="x",
                base_risk=50,
                expected_post_state={},
            )
        )


# --- measurement --------------------------------------------------------------


def test_the_uncertain_environment_rate_leads_the_summary() -> None:
    """A system that resolves 95% and leaves the environment unknown for the
    other 5% is not 95% good, it is unfit."""
    quality = score_remediations(
        [
            Remediation("a", Disposition.RESOLVED),
            Remediation("b", Disposition.ROLLBACK_FAILED),
        ]
    )
    keys = list(quality.summary())
    assert keys[0] == "rollback_failed"
    assert keys.index("uncertain_environment_rate") < keys.index("resolved")
    assert quality.uncertain_environment_rate == 0.5


def test_scoring_counts_every_disposition() -> None:
    quality = score_remediations(
        [
            Remediation("a", Disposition.RESOLVED),
            Remediation("b", Disposition.ROLLED_BACK),
            Remediation("c", Disposition.ESCALATED),
            Remediation("d", Disposition.BLOCKED),
            Remediation("e", Disposition.ROLLBACK_FAILED),
        ]
    )
    assert quality.total == 5
    assert quality.autonomous_resolution_rate == 0.2
