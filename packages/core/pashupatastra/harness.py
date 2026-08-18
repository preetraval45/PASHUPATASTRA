"""Benchmark harness — run bookkeeping, variance, and exclusions.

The parts that touch a cluster live in `benchmark/harness/`. What is here is the
logic that decides what a run means, which is worth testing without needing
infrastructure to do it.

Two things this module refuses to let the harness do quietly.

A scenario the harness cannot inject is **excluded with a stated reason**, never
skipped. Silently dropping the cases that are hard to reproduce reports a subset
as though it were the corpus, and the subset is biased in the worst possible
direction — toward the scenarios that were easy to build.

Results are reported **per scenario across N runs**, not as a mean. A scenario
that resolves 3 times in 5 and one that resolves 5 times in 5 average out to
"mostly fine", and only one of them is a system you would turn on.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from .pib import Outcome, PibScenario


class Arm(StrEnum):
    """Who or what is being measured. Recorded from the start so results from
    different arms can never be pooled by accident."""

    PASHUPATASTRA = "pashupatastra"
    NAIVE_LLM = "naive_llm"
    RUNBOOK = "runbook"
    HUMAN = "human"


class Verdict(StrEnum):
    """How one run turned out, graded against what the scenario expected."""

    CORRECT = "correct"
    WRONG_ACTION = "wrong_action"
    """Acted, but not as the scenario expected."""

    FALSE_REMEDIATION = "false_remediation"
    """Acted on a negative case, or took a forbidden action. The most expensive
    failure the benchmark measures, and the one reported first."""

    MISSED = "missed"
    """A real incident that produced no action and no escalation."""

    FAILED_TO_ESCALATE = "failed_to_escalate"
    HARNESS_ERROR = "harness_error"
    """The run did not produce an answer. Not evidence about the system."""

    @property
    def is_correct(self) -> bool:
        return self is Verdict.CORRECT

    @property
    def scoreable(self) -> bool:
        """A harness error says something about the harness, and folding it into
        the failure rate would make a flaky rig look like a wrong system."""
        return self is not Verdict.HARNESS_ERROR


@dataclass(frozen=True)
class RunResult:
    """One execution of one scenario."""

    scenario_id: str
    arm: Arm
    run_index: int
    verdict: Verdict
    action_taken: str | None = None
    escalated: bool = False
    duration_seconds: float = 0.0
    detail: str = ""


def grade(
    scenario: PibScenario,
    action_taken: str | None,
    escalated: bool,
) -> Verdict:
    """Compare what happened to what the scenario said should happen.

    Forbidden actions are checked before anything else: taking one is a false
    remediation even if the incident happened to resolve, because a benchmark
    that forgives a prohibited action when it works is measuring luck.
    """
    if action_taken and action_taken in scenario.constraints.forbidden_actions:
        return Verdict.FALSE_REMEDIATION

    if scenario.outcome is Outcome.NOTHING:
        # Escalating a benign event is noise rather than damage, so it is graded
        # as a wrong answer rather than as a false remediation.
        if action_taken:
            return Verdict.FALSE_REMEDIATION
        return Verdict.WRONG_ACTION if escalated else Verdict.CORRECT

    if scenario.outcome is Outcome.ESCALATE:
        if action_taken:
            return Verdict.FALSE_REMEDIATION
        return Verdict.CORRECT if escalated else Verdict.FAILED_TO_ESCALATE

    if action_taken is None:
        return Verdict.MISSED if not escalated else Verdict.FAILED_TO_ESCALATE
    if action_taken not in scenario.constraints.allowed_actions:
        return Verdict.FALSE_REMEDIATION
    return Verdict.CORRECT if action_taken == scenario.expected.action else Verdict.WRONG_ACTION


@dataclass
class ScenarioRuns:
    """Every run of one scenario under one arm."""

    scenario_id: str
    arm: Arm
    runs: list[RunResult] = field(default_factory=list)

    @property
    def scoreable(self) -> list[RunResult]:
        return [r for r in self.runs if r.verdict.scoreable]

    @property
    def correct(self) -> int:
        return sum(1 for r in self.scoreable if r.verdict.is_correct)

    @property
    def attempted(self) -> int:
        return len(self.scoreable)

    @property
    def harness_errors(self) -> int:
        return len(self.runs) - len(self.scoreable)

    @property
    def rate(self) -> float:
        return round(self.correct / self.attempted, 4) if self.attempted else 0.0

    @property
    def unstable(self) -> bool:
        """Some runs correct, some not. The single most useful thing N runs buys:
        a scenario that only sometimes works is not a scenario that works, and an
        aggregate mean is exactly where that disappears."""
        return 0 < self.correct < self.attempted

    @property
    def duration_stdev(self) -> float:
        times = [r.duration_seconds for r in self.scoreable]
        return round(statistics.stdev(times), 3) if len(times) > 1 else 0.0

    @property
    def verdicts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for run in self.runs:
            counts[run.verdict.value] = counts.get(run.verdict.value, 0) + 1
        return dict(sorted(counts.items()))


@dataclass(frozen=True)
class Exclusion:
    """A scenario the harness did not run, and why.

    The reason is mandatory. An excluded scenario with no reason is
    indistinguishable from one that was quietly dropped for being inconvenient.
    """

    scenario_id: str
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError(
                f"{self.scenario_id}: an exclusion must state its reason — "
                "an unexplained exclusion is a silent skip with extra steps"
            )


@dataclass
class HarnessReport:
    arm: Arm
    runs_per_scenario: int
    scenarios: list[ScenarioRuns] = field(default_factory=list)
    exclusions: list[Exclusion] = field(default_factory=list)

    @property
    def attempted_scenarios(self) -> int:
        return len(self.scenarios)

    @property
    def coverage(self) -> float:
        """Share of the corpus actually run. Reported next to every result, so a
        headline number can never be read without the denominator it came from."""
        total = self.attempted_scenarios + len(self.exclusions)
        return round(self.attempted_scenarios / total, 4) if total else 0.0

    @property
    def unstable_scenarios(self) -> list[str]:
        return [s.scenario_id for s in self.scenarios if s.unstable]

    @property
    def false_remediations(self) -> int:
        return sum(
            1
            for s in self.scenarios
            for r in s.runs
            if r.verdict is Verdict.FALSE_REMEDIATION
        )

    @property
    def correct_runs(self) -> int:
        return sum(s.correct for s in self.scenarios)

    @property
    def scoreable_runs(self) -> int:
        return sum(s.attempted for s in self.scenarios)

    @property
    def harness_errors(self) -> int:
        return sum(s.harness_errors for s in self.scenarios)

    @property
    def false_remediation_rate(self) -> float:
        return (
            round(self.false_remediations / self.scoreable_runs, 4)
            if self.scoreable_runs
            else 0.0
        )

    @property
    def correct_rate(self) -> float:
        return (
            round(self.correct_runs / self.scoreable_runs, 4) if self.scoreable_runs else 0.0
        )

    def summary(self) -> dict[str, object]:
        """Ordered deliberately: the failure rate before the success rate, per
        the reporting rule in the roadmap. Whichever number is read first is the
        one that gets quoted."""
        return {
            "arm": self.arm.value,
            "runs_per_scenario": self.runs_per_scenario,
            "false_remediation_rate": self.false_remediation_rate,
            "false_remediations": self.false_remediations,
            "correct_rate": self.correct_rate,
            "correct_runs": self.correct_runs,
            "scoreable_runs": self.scoreable_runs,
            "harness_errors": self.harness_errors,
            "scenarios_attempted": self.attempted_scenarios,
            "scenarios_excluded": len(self.exclusions),
            "coverage": self.coverage,
            "unstable_scenarios": self.unstable_scenarios,
        }


def collect(
    arm: Arm,
    runs_per_scenario: int,
    results: Iterable[RunResult],
    exclusions: Iterable[Exclusion] = (),
) -> HarnessReport:
    by_scenario: dict[str, ScenarioRuns] = {}
    for result in results:
        entry = by_scenario.setdefault(
            result.scenario_id, ScenarioRuns(result.scenario_id, arm)
        )
        entry.runs.append(result)

    return HarnessReport(
        arm=arm,
        runs_per_scenario=runs_per_scenario,
        scenarios=[by_scenario[k] for k in sorted(by_scenario)],
        exclusions=list(exclusions),
    )
