"""Run the PIB corpus against a live cluster. One command.

    python -m benchmark.harness.run --runs 3 --arm none

Arms here are the two trivial baselines: `none` never acts, `always-act` always
restarts something. The real arms are 5.3. These two exist because a harness
that has never distinguished anything is not known to work — `none` should ace
every negative case and fail every remediation, `always-act` the reverse, and if
both score alike the rig is broken rather than the systems being equal.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable

sys.path.insert(0, "packages/core")
sys.path.insert(0, ".")

from benchmark.harness.inject import excluded_reason, inject  # noqa: E402
from benchmark.harness.stack import EphemeralStack, StackError  # noqa: E402
from pashupatastra.harness import (  # noqa: E402
    Arm,
    Exclusion,
    RunResult,
    Verdict,
    collect,
    grade,
)
from pashupatastra.pib import Outcome, PibScenario, load_corpus  # noqa: E402

# An arm decides what to do, given the scenario and the live stack. It returns
# (action_taken, escalated) — never both, and either may be empty.
ArmFn = Callable[[PibScenario, EphemeralStack], tuple[str | None, bool]]


def arm_none(scenario: PibScenario, stack: EphemeralStack) -> tuple[str | None, bool]:
    return None, False


def arm_always_act(scenario: PibScenario, stack: EphemeralStack) -> tuple[str | None, bool]:
    return "restart_service", False


ARMS: dict[str, ArmFn] = {"none": arm_none, "always-act": arm_always_act}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=1, help="repetitions per scenario")
    parser.add_argument("--arm", choices=sorted(ARMS), default="none")
    parser.add_argument("--context", default=None, help="kubeconfig context")
    parser.add_argument("--corpus", default="benchmark/incidents/pib")
    parser.add_argument("--limit", type=int, default=0, help="cap scenarios (smoke runs)")
    parser.add_argument(
        "--plan", action="store_true", help="report coverage and exit without touching a cluster"
    )
    args = parser.parse_args()

    corpus = load_corpus(args.corpus)
    runnable: list[PibScenario] = []
    exclusions: list[Exclusion] = []
    for scenario in corpus:
        if reason := excluded_reason(scenario):
            exclusions.append(Exclusion(scenario.id, reason))
        else:
            runnable.append(scenario)

    if args.limit:
        dropped = runnable[args.limit :]
        runnable = runnable[: args.limit]
        exclusions += [
            Exclusion(s.id, f"not run: --limit {args.limit} was set for this run")
            for s in dropped
        ]

    _print_plan(corpus, runnable, exclusions)
    if args.plan:
        return 0

    arm_fn = ARMS[args.arm]
    arm = Arm.PASHUPATASTRA if args.arm not in ARMS else Arm.RUNBOOK
    results: list[RunResult] = []

    print(f"\nrunning {len(runnable)} scenarios x {args.runs} against arm '{args.arm}'\n")
    for index, scenario in enumerate(runnable, 1):
        for run_index in range(args.runs):
            result = run_once(scenario, arm, run_index, arm_fn, args.context)
            results.append(result)
            flag = "" if result.verdict.is_correct else f"  <- {result.verdict.value}"
            print(
                f"  [{index}/{len(runnable)}] {scenario.id} run {run_index + 1}"
                f"  {result.verdict.value}{flag}"
            )

    report = collect(arm, args.runs, results, exclusions)
    _print_report(report, args.arm)
    return 0


def run_once(
    scenario: PibScenario,
    arm: Arm,
    run_index: int,
    arm_fn: ArmFn,
    context: str | None,
) -> RunResult:
    """One scenario, one repetition, in its own namespace."""
    run_id = f"{scenario.id.lower()}-{run_index}"
    started = time.monotonic()
    try:
        with EphemeralStack(run_id, context=context) as stack:
            injection = inject(scenario, stack)
            action, escalated = arm_fn(scenario, stack)
            verdict = grade(scenario, action, escalated)
            return RunResult(
                scenario_id=scenario.id,
                arm=arm,
                run_index=run_index,
                verdict=verdict,
                action_taken=action,
                escalated=escalated,
                duration_seconds=round(time.monotonic() - started, 2),
                detail=injection.describe,
            )
    except (StackError, ValueError, OSError) as error:
        # Graded as a harness error, which is excluded from the failure rate. A
        # rig that could not set up the fault has said nothing about the system,
        # and folding it into the score would make a flaky cluster look like a
        # wrong answer.
        return RunResult(
            scenario_id=scenario.id,
            arm=arm,
            run_index=run_index,
            verdict=Verdict.HARNESS_ERROR,
            duration_seconds=round(time.monotonic() - started, 2),
            detail=f"{type(error).__name__}: {error}",
        )


def _print_plan(corpus, runnable, exclusions) -> None:
    by_outcome: dict[str, int] = {}
    for s in runnable:
        by_outcome[s.outcome.value] = by_outcome.get(s.outcome.value, 0) + 1

    print(f"PIB harness — {len(runnable)} of {len(corpus)} scenarios runnable "
          f"({round(100 * len(runnable) / len(corpus))}%)")
    print(f"  runnable by outcome: {dict(sorted(by_outcome.items()))}")

    # Stated every time, because it is the thing a headline number from this
    # subset would hide.
    remediate = by_outcome.get(Outcome.REMEDIATE.value, 0)
    if remediate < len(runnable) / 3:
        print(
            "\n  NOTE: the runnable subset is weighted towards cases whose correct\n"
            "  answer is to do nothing or hand off. It under-tests remediation, so a\n"
            "  score from this subset flatters restraint and is not a corpus score."
        )

    reasons: dict[str, int] = {}
    for exclusion in exclusions:
        head = exclusion.reason.split(":")[0].split(",")[0]
        reasons[head] = reasons.get(head, 0) + 1
    print(f"\n  excluded {len(exclusions)}:")
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"    {count:>3}  {reason}")


def _print_report(report, arm_name: str) -> None:
    summary = report.summary()
    print(f"\n--- {arm_name} ---")
    # Failure rate first, deliberately: whichever number is read first is the
    # one that gets quoted.
    print(f"  false remediation rate : {summary['false_remediation_rate']}"
          f"  ({summary['false_remediations']} runs)")
    print(f"  correct rate           : {summary['correct_rate']}"
          f"  ({summary['correct_runs']}/{summary['scoreable_runs']} runs)")
    print(f"  harness errors         : {summary['harness_errors']}")
    print(f"  coverage               : {summary['coverage']} "
          f"({summary['scenarios_attempted']} run, {summary['scenarios_excluded']} excluded)")
    if unstable := summary["unstable_scenarios"]:
        print(f"  unstable scenarios     : {unstable}")
    else:
        print("  unstable scenarios     : none")

    print("\n  per scenario:")
    for entry in report.scenarios:
        marker = " UNSTABLE" if entry.unstable else ""
        print(f"    {entry.scenario_id}  {entry.correct}/{entry.attempted}"
              f"  {entry.verdicts}{marker}")


if __name__ == "__main__":
    raise SystemExit(main())
