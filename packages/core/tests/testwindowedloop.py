"""The window feeding the remediation loop.

Tested here rather than in testobservation because the thing worth proving is
the seam: a window that never held has to reach the loop as a failure and
trigger the rollback, not just as a lower-level verdict nobody acts on.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pashupatastra.dharma import ActionSpec, Tier, Verdict
from pashupatastra.incidents import VerificationCheck
from pashupatastra.observation import Window, WindowObserver, as_checks
from pashupatastra.remediation import Disposition, Remediator

START = datetime(2026, 8, 18, 15, 0, 0).astimezone()
WINDOW = Window(
    settle=timedelta(0), timeout=timedelta(seconds=60),
    interval=timedelta(seconds=5), hold_samples=3,
)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def check(passed: bool) -> list[VerificationCheck]:
    return [
        VerificationCheck(
            name="rollout",
            expected="complete",
            observed="complete" if passed else "progressing",
            passed=passed,
        )
    ]


def an_action(action_id: str = "rollback_deployment") -> ActionSpec:
    """A genuine rollback pair, matching testremediation's fixture."""
    return ActionSpec(
        id=action_id,
        description="test",
        base_risk=10,
        expected_post_state={"rollout": "complete"},
        rollback_action_id="redeploy_version",
    )


def a_verdict() -> Verdict:
    return Verdict(
        action_id="rollback_deployment",
        incident_ref="INC-1",
        base_risk=10,
        adjustments=[],
        effective_risk=10,
        tier=Tier.AUTONOMOUS,
        required_approvers=[],
        expires_at=START + timedelta(minutes=15),
    )


def loop_over(samples: list[list[VerificationCheck]]) -> tuple[Disposition, list[str]]:
    """Run the remediation loop with a windowed observer over scripted samples."""
    clock = Clock()
    sequence = iter(samples)
    last = samples[-1]
    ran: list[str] = []

    def runner(action: ActionSpec, params: dict[str, str]) -> str:
        ran.append(action.id)
        return "ok"

    def observer(action: ActionSpec, params: dict[str, str]) -> list[VerificationCheck]:
        watcher = WindowObserver(clock=clock, sleep=clock.sleep)
        # The scripted samples describe the action under test. A rollback is
        # verified through this same observer, and letting it read the tail of an
        # exhausted script would grade every undo as failed.
        sampler = (
            (lambda: check(True))
            if action.id == "redeploy_version"
            else (lambda: next(sequence, last))
        )
        return as_checks(watcher.watch(action.id, sampler, WINDOW))

    remediator = Remediator(
        runner=runner,
        observer=observer,
        rollback_of=lambda action_id: an_action("redeploy_version"),
        clock=lambda: START,
    )
    result = remediator.remediate(an_action(), a_verdict(), {})
    return result.disposition, ran


def test_a_sustained_recovery_resolves_without_rolling_back() -> None:
    disposition, ran = loop_over([check(True)] * 3)
    assert disposition is Disposition.RESOLVED
    assert ran == ["rollback_deployment"], "nothing should be undone"


def test_a_flapping_window_rolls_back_even_though_it_passed_samples() -> None:
    """The regression this seam exists to prevent.

    Handing the loop only the last sample would let a metric that was merely
    bouncing close the incident. It has to see the window verdict.
    """
    disposition, ran = loop_over([check(True), check(False)] * 6)
    assert disposition is Disposition.ROLLED_BACK
    assert "redeploy_version" in ran, "the rollback must actually run"


def test_a_state_never_reached_rolls_back() -> None:
    disposition, ran = loop_over([check(False)] * 12)
    assert disposition is Disposition.ROLLED_BACK
    assert "redeploy_version" in ran
