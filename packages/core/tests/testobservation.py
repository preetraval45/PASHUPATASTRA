"""Post-action observation windows.

The interesting cases are the ones a single-shot check gets wrong: the state
that has not settled yet, the state that passes once while bouncing, and the
state that recovers and then degrades again. Each has a different correct
answer, and a boolean cannot carry the difference.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pashupatastra.incidents import VerificationCheck
from pashupatastra.observation import (
    SETTLING_CHECK,
    as_checks,
    DEFAULT_WINDOW,
    WINDOWS,
    Settling,
    Window,
    WindowObserver,
    window_for,
)

START = datetime(2026, 8, 18, 15, 0, 0).astimezone()


def passing() -> list[VerificationCheck]:
    return [VerificationCheck(name="health", expected="healthy", observed="healthy", passed=True)]


def failing() -> list[VerificationCheck]:
    return [VerificationCheck(name="health", expected="healthy", observed="crashloop", passed=False)]


def unobserved() -> list[VerificationCheck]:
    return [VerificationCheck(name="health", expected="healthy", observed=None, passed=None)]


class Clock:
    """Advances only when the observer sleeps â€” so tests run instantly."""

    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def watch(results: list[list[VerificationCheck]], window: Window | None = None):
    """Run a window against a scripted sequence of observations."""
    clock = Clock()
    sequence = iter(results)
    last = results[-1] if results else failing()

    def sampler() -> list[VerificationCheck]:
        return next(sequence, last)

    observer = WindowObserver(clock=clock, sleep=clock.sleep)
    return observer.watch("restart_service", sampler, window or Window(
        settle=timedelta(seconds=10), timeout=timedelta(seconds=60),
        interval=timedelta(seconds=5), hold_samples=3,
    ))


# --- the state must hold, not merely occur -----------------------------------


def test_a_sustained_recovery_verifies() -> None:
    result = watch([passing(), passing(), passing()])
    assert result.settling is Settling.HELD
    assert result.verified


def test_one_passing_sample_is_not_recovery() -> None:
    """Error rate dipping once during a restart looks identical to error rate
    being fixed. Accepting the first pass closes the incident while the fault is
    still there â€” the most expensive false result available, because it stops
    anyone looking."""
    result = watch([passing(), failing(), failing(), failing(), failing(),
                    failing(), failing(), failing(), failing(), failing()])
    assert not result.verified
    assert result.ever_passed, "it did pass once"
    assert result.longest_hold == 1


def test_a_run_that_falls_one_short_is_reported_as_such() -> None:
    """"Held for two of three required" and "never passed once" are both failures
    that look the same in a boolean, and lead somewhere different."""
    result = watch([passing(), passing(), failing()] * 6)
    assert not result.verified
    assert result.longest_hold == 2
    assert "longest run 2 of 3" in result.describe()


# --- the failure modes are named ---------------------------------------------


def test_never_reaching_the_state_is_distinct_from_flapping() -> None:
    result = watch([failing()] * 12)
    assert result.settling is Settling.NEVER_REACHED
    assert not result.ever_passed


def test_oscillation_is_reported_as_flapping() -> None:
    """The system is recovering and degrading repeatedly. The action may be
    working against something still unstable, and the operator's next move
    differs from a clean failure."""
    result = watch([passing(), failing()] * 6)
    assert result.settling is Settling.FLAPPING
    assert "oscillating" in result.describe()


def test_recovering_then_degrading_once_is_a_regression() -> None:
    """Often the signature of a fix that holds only until load returns."""
    result = watch([passing(), passing(), failing(), failing(), failing(),
                    failing(), failing(), failing(), failing(), failing(),
                    failing(), failing()])
    assert result.settling is Settling.REGRESSED
    assert "then lost" in result.describe()


# --- settle time --------------------------------------------------------------


def test_nothing_is_sampled_during_settle() -> None:
    """A rollout restart has not finished when the command returns. Querying then
    sees the old pods, grades a failure, and rolls back something that worked."""
    clock = Clock()
    sampled_at: list[datetime] = []

    def sampler() -> list[VerificationCheck]:
        sampled_at.append(clock.now)
        return passing()

    WindowObserver(clock=clock, sleep=clock.sleep).watch(
        "restart_service",
        sampler,
        Window(settle=timedelta(seconds=30), timeout=timedelta(seconds=120),
               interval=timedelta(seconds=5), hold_samples=1),
    )
    assert sampled_at[0] - START >= timedelta(seconds=30)


def test_a_window_with_no_settle_samples_immediately() -> None:
    """Delivery of a notification has nothing to settle."""
    clock = Clock()
    seen: list[datetime] = []

    def sampler() -> list[VerificationCheck]:
        seen.append(clock.now)
        return passing()

    WindowObserver(clock=clock, sleep=clock.sleep).watch(
        "notify_engineer", sampler, WINDOWS["notify_engineer"]
    )
    assert seen[0] == START


# --- unobserved is not failed, and never successful --------------------------


def test_an_unobservable_check_never_counts_as_a_pass() -> None:
    result = watch([unobserved()] * 12)
    assert not result.verified
    assert not result.ever_passed


def test_a_sampler_that_raises_produces_an_unobserved_sample() -> None:
    """An observer that cannot see is the distinction this module rests on."""
    clock = Clock()

    def sampler() -> list[VerificationCheck]:
        raise ConnectionError("prometheus unreachable")

    result = WindowObserver(clock=clock, sleep=clock.sleep).watch(
        "restart_service",
        sampler,
        Window(settle=timedelta(0), timeout=timedelta(seconds=20),
               interval=timedelta(seconds=5)),
    )
    assert not result.verified
    assert "unobservable" in (result.samples[0].checks[0].observed or "")
    assert result.samples[0].checks[0].passed is None


def test_no_checks_at_all_is_not_a_pass() -> None:
    """Claiming success with no evidence is what the whole layer prevents."""
    result = watch([[]] * 12)
    assert not result.verified


def test_still_passing_when_the_window_closed_is_inconclusive_not_a_regression() -> None:
    """Nothing was lost â€” it ran out of time mid-recovery and might have held
    given longer.

    Calling that a regression would blame the action for the window being too
    short, and send an operator looking for a fault that had already cleared.
    """
    clock = Clock()
    result = WindowObserver(clock=clock, sleep=clock.sleep).watch(
        "restart_service",
        lambda: passing(),
        # Only one sample fits before the window closes.
        Window(settle=timedelta(seconds=59), timeout=timedelta(seconds=60),
               interval=timedelta(seconds=5), hold_samples=3),
    )
    assert result.settling is Settling.TIMED_OUT
    assert not result.verified, "inconclusive is still not success"
    assert result.ever_passed
    assert "unobserved, not successful" in result.describe()


def test_a_late_failure_after_recovery_is_still_a_regression() -> None:
    """The distinction is which side it ended on, not merely that it passed."""
    result = watch([passing(), passing(), failing()] + [failing()] * 9)
    assert result.settling is Settling.REGRESSED


# --- per-action windows -------------------------------------------------------


def test_a_rollback_gets_longer_than_a_restart() -> None:
    """It pulls an image and drains connections. One window for both would be
    wrong for one of them."""
    assert window_for("rollback_deployment").timeout > window_for("restart_service").timeout
    assert window_for("rollback_deployment").settle > window_for("restart_service").settle


def test_a_cache_flush_waits_for_the_hit_rate_not_the_command() -> None:
    """Applying is instant; the effect the post-state claims is not."""
    cache = window_for("clear_cache")
    assert cache.settle >= timedelta(seconds=30)
    assert cache.hold_samples > DEFAULT_WINDOW.hold_samples


def test_an_unknown_action_gets_a_window_rather_than_an_error() -> None:
    """A new action nobody tuned should still be verified. Erroring here would
    mean an unverified execution, which is the worse failure."""
    assert window_for("some_future_action") == DEFAULT_WINDOW


def test_every_registered_action_with_a_post_state_has_a_window() -> None:
    """An action declaring an expected post-state is claiming it is verifiable."""
    from pashupatastra.registry import all_actions

    for action in all_actions():
        if action.expected_post_state:
            assert window_for(action.id) is not None


# --- window validity ----------------------------------------------------------


def test_a_timeout_inside_settle_is_rejected() -> None:
    """Otherwise nothing is ever sampled and every action silently times out."""
    with pytest.raises(ValueError, match="timeout must exceed settle"):
        Window(settle=timedelta(seconds=60), timeout=timedelta(seconds=30))


def test_hold_samples_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        Window(settle=timedelta(0), timeout=timedelta(seconds=10), hold_samples=0)


def test_the_default_requires_more_than_one_sample() -> None:
    """Three is the smallest number that distinguishes a sustained state from a
    bounce plus luck."""
    assert DEFAULT_WINDOW.hold_samples >= 3


def test_the_last_sample_is_what_an_operator_reads() -> None:
    result = watch([failing(), passing(), passing(), passing()])
    assert result.to_checks()[0].passed is True


# --- feeding the remediation loop ---------------------------------------------


def test_the_window_verdict_travels_as_its_own_check() -> None:
    """The loop grades by requiring every check to pass. Handing it only the last
    sample would lose the window: a flapping metric that happened to be up on the
    final observation would present as a clean pass."""
    result = watch([passing(), failing()] * 6)
    checks = as_checks(result)

    assert result.settling is Settling.FLAPPING
    settling = next(c for c in checks if c.name == SETTLING_CHECK)
    assert settling.passed is False
    assert not all(c.passed for c in checks), "the loop must see this as a failure"


def test_a_held_window_produces_an_all_passing_check_set() -> None:
    checks = as_checks(watch([passing(), passing(), passing()]))
    assert all(check.passed for check in checks)


def test_the_synthetic_check_is_distinguishable_from_an_observation() -> None:
    """A reader scanning a verification record should be able to tell which lines
    came from the world and which are this module's judgement about it."""
    checks = as_checks(watch([passing(), passing(), passing()]))
    settling = next(c for c in checks if c.name == SETTLING_CHECK)
    assert "consecutive samples" in settling.expected


def test_a_last_sample_that_passes_cannot_smuggle_a_failed_window_through() -> None:
    """Ends on a good sample, never holds three. Must still fail."""
    result = watch([failing(), passing()] * 6)
    checks = as_checks(result)
    assert result.samples[-1].passed
    assert not result.verified
    assert not all(c.passed for c in checks)

