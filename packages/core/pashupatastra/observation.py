"""Post-action verification over a window, rather than a single check.

Two things a one-shot check gets wrong: it reads the pre-settled state if you
call it immediately, and it accepts a metric that is merely bouncing. So we wait
out a settle period, then require the expected state to hold for several
consecutive samples.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from .incidents import VerificationCheck


class Settling(StrEnum):
    HELD = "held"
    NEVER_REACHED = "never_reached"
    FLAPPING = "flapping"
    REGRESSED = "regressed"
    TIMED_OUT = "timed_out"

    @property
    def verified(self) -> bool:
        return self is Settling.HELD


@dataclass(frozen=True)
class Window:
    settle: timedelta
    """Nothing is sampled before this — the action has not taken effect yet."""

    timeout: timedelta
    interval: timedelta = timedelta(seconds=5)

    hold_samples: int = 3
    """Consecutive passes required. One pass can be a bounce."""

    def __post_init__(self) -> None:
        if self.timeout <= self.settle:
            raise ValueError("timeout must exceed settle, or nothing is ever sampled")
        if self.hold_samples < 1:
            raise ValueError("hold_samples must be at least 1")


DEFAULT_WINDOW = Window(settle=timedelta(seconds=10), timeout=timedelta(minutes=2))

# Settle times differ by what the action actually has to do: a pod restart is
# seconds, a rollback pulls an image and drains connections, and a cache flush
# applies instantly but its hit rate takes minutes to recover.
WINDOWS: dict[str, Window] = {
    "restart_service": Window(settle=timedelta(seconds=10), timeout=timedelta(minutes=2)),
    "scale_service": Window(settle=timedelta(seconds=15), timeout=timedelta(minutes=3)),
    "rollback_deployment": Window(settle=timedelta(seconds=30), timeout=timedelta(minutes=5)),
    "redeploy_version": Window(settle=timedelta(seconds=30), timeout=timedelta(minutes=5)),
    "disable_deployment": Window(settle=timedelta(seconds=5), timeout=timedelta(minutes=1)),
    "clear_cache": Window(
        settle=timedelta(seconds=30), timeout=timedelta(minutes=5), hold_samples=4
    ),
    "warm_cache": Window(settle=timedelta(seconds=30), timeout=timedelta(minutes=5)),
    "notify_engineer": Window(settle=timedelta(0), timeout=timedelta(seconds=10), hold_samples=1),
    "create_ticket": Window(settle=timedelta(0), timeout=timedelta(seconds=10), hold_samples=1),
}


def window_for(action_id: str) -> Window:
    """An untuned action still gets verified, just not optimally."""
    return WINDOWS.get(action_id, DEFAULT_WINDOW)


@dataclass
class Sample:
    at: datetime
    checks: list[VerificationCheck]

    @property
    def passed(self) -> bool:
        # An unobserved check counts against, never for.
        return bool(self.checks) and all(check.passed is True for check in self.checks)

    @property
    def unobserved(self) -> list[str]:
        return [check.name for check in self.checks if check.passed is None]


@dataclass
class WindowResult:
    action_id: str
    settling: Settling
    samples: list[Sample] = field(default_factory=list)
    window: Window = DEFAULT_WINDOW

    @property
    def verified(self) -> bool:
        return self.settling.verified

    @property
    def longest_hold(self) -> int:
        """Reported because "held 2 of 3" and "never passed" mean different things."""
        best = current = 0
        for sample in self.samples:
            current = current + 1 if sample.passed else 0
            best = max(best, current)
        return best

    @property
    def ever_passed(self) -> bool:
        return any(sample.passed for sample in self.samples)

    def describe(self) -> str:
        match self.settling:
            case Settling.HELD:
                return (
                    f"{self.action_id}: held for {self.window.hold_samples} consecutive samples"
                )
            case Settling.NEVER_REACHED:
                return (
                    f"{self.action_id}: expected state never observed across "
                    f"{len(self.samples)} samples"
                )
            case Settling.FLAPPING:
                return (
                    f"{self.action_id}: reached but never held — longest run "
                    f"{self.longest_hold} of {self.window.hold_samples} required. "
                    "The system is oscillating rather than recovering"
                )
            case Settling.REGRESSED:
                return f"{self.action_id}: reached, then lost and not regained"
            case _:
                return (
                    f"{self.action_id}: window closed after {self.window.timeout} "
                    "without a conclusion — unobserved, not successful"
                )

    def to_checks(self) -> list[VerificationCheck]:
        return self.samples[-1].checks if self.samples else []


Sampler = Callable[[], list[VerificationCheck]]

SETTLING_CHECK = "sustained"


def as_checks(result: WindowResult) -> list[VerificationCheck]:
    """Render for the remediation loop, which grades by requiring every check to pass.

    The window verdict has to travel as its own check — otherwise a flapping
    metric that happened to be up on the last sample reads as a clean pass.
    """
    return [
        *result.to_checks(),
        VerificationCheck(
            name=SETTLING_CHECK,
            expected=f"held for {result.window.hold_samples} consecutive samples",
            observed=result.describe(),
            passed=result.verified,
        ),
    ]


class WindowObserver:
    """Clock and sleep are injected so tests run in microseconds, not minutes."""

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._now = clock or (lambda: datetime.now().astimezone())
        self._sleep = sleep or (lambda _seconds: None)

    def watch(self, action_id: str, sampler: Sampler, window: Window | None = None) -> WindowResult:
        window = window or window_for(action_id)
        started = self._now()
        result = WindowResult(action_id=action_id, settling=Settling.TIMED_OUT, window=window)

        if window.settle.total_seconds() > 0:
            self._sleep(window.settle.total_seconds())

        consecutive = 0
        while self._now() - started < window.timeout:
            try:
                checks = sampler()
            except Exception as error:  # noqa: BLE001
                # Cannot see is not the same as failed.
                checks = [
                    VerificationCheck(
                        name="observation",
                        expected="observable",
                        observed=f"unobservable: {type(error).__name__}: {error}",
                    )
                ]

            sample = Sample(at=self._now(), checks=checks)
            result.samples.append(sample)

            consecutive = consecutive + 1 if sample.passed else 0
            if consecutive >= window.hold_samples:
                result.settling = Settling.HELD
                return result

            self._sleep(window.interval.total_seconds())

        result.settling = self._classify(result)
        return result

    @staticmethod
    def _classify(result: WindowResult) -> Settling:
        if not result.samples:
            return Settling.TIMED_OUT
        if not result.ever_passed:
            return Settling.NEVER_REACHED

        crossings = sum(
            1
            for earlier, later in zip(result.samples, result.samples[1:])
            if earlier.passed != later.passed
        )

        # Checked before the ending-side test: a metric crossing repeatedly is
        # unstable regardless of which side the last sample landed on, and
        # letting the ending decide would make the verdict depend on the
        # sampling interval.
        if crossings > 1:
            return Settling.FLAPPING

        # Still passing at the close, no oscillation behind it. Nothing was lost;
        # it just ran out of time and might have held.
        if result.samples[-1].passed:
            return Settling.TIMED_OUT

        return Settling.REGRESSED
