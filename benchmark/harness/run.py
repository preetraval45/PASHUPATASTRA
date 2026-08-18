"""Run the PIB corpus against a live cluster. One command.

    python -m benchmark.harness.run --runs 3 --arm pashupatastra

Arms never receive the scenario. They receive a `Brief` — live stack state, the
actions they may take, and the ceiling they work under — because the scenario
carries `expected.action`, and an arm holding the answer key would score
perfectly while measuring nothing.

`none` and `always-act` are kept as rig checks rather than results: a harness
that has never distinguished anything is not known to work, so the two of them
should score exactly opposite on the same scenarios.
"""

from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, "packages/core")
sys.path.insert(0, ".")

from benchmark.harness.arms import (  # noqa: E402
    GATED,
    ArmUnavailable,
    PashupatastraArm,
    RunbookArm,
)
from benchmark.harness.inject import excluded_reason, inject  # noqa: E402
from benchmark.harness.stack import EphemeralStack, StackError  # noqa: E402
from pashupatastra.arms import Brief, Decision, brief_for  # noqa: E402
from pashupatastra.harness import (  # noqa: E402
    Arm,
    Exclusion,
    RunResult,
    Verdict,
    collect,
    grade,
)
from pashupatastra.pib import Outcome, PibScenario, load_corpus  # noqa: E402


class NoneArm:
    """Rig check: never acts. Should ace every negative and fail every remediation."""

    name = "none"

    def decide(self, brief: Brief) -> Decision:
        return Decision(rationale="rig check: does nothing")


class AlwaysActArm:
    """Rig check: always acts. Should be the exact inverse of `none`."""

    name = "always-act"

    def decide(self, brief: Brief) -> Decision:
        return Decision(action="restart_service", rationale="rig check: always acts")


def build_arm(name: str, stack: EphemeralStack | None):
    if name == "none":
        return NoneArm()
    if name == "always-act":
        return AlwaysActArm()
    if name == "runbook":
        return RunbookArm()
    if name == "pashupatastra":
        return PashupatastraArm(stack=stack)
    return GATED[name]()


ARM_NAMES = ("none", "always-act", "runbook", "pashupatastra", "naive-llm", "human")
ARM_KIND = {
    "runbook": Arm.RUNBOOK,
    "pashupatastra": Arm.PASHUPATASTRA,
    "naive-llm": Arm.NAIVE_LLM,
    "human": Arm.HUMAN,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=1, help="repetitions per scenario")
    parser.add_argument("--arm", choices=ARM_NAMES, default="pashupatastra")
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

    if args.arm in GATED:
        try:
            build_arm(args.arm, None).decide(
                Brief(scenario_id="probe", stack="", allowed_actions=(),
                      forbidden_actions=(), risk_ceiling=0)
            )
        except ArmUnavailable as error:
            print(f"\nARM UNAVAILABLE — {args.arm}\n  {error}")
            return 2

    arm = ARM_KIND.get(args.arm, Arm.RUNBOOK)
    results: list[RunResult] = []

    print(f"\nrunning {len(runnable)} scenarios x {args.runs} against arm '{args.arm}'\n")
    for index, scenario in enumerate(runnable, 1):
        for run_index in range(args.runs):
            result = run_once(scenario, arm, run_index, args.arm, args.context)
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
    arm_name: str,
    context: str | None,
) -> RunResult:
    """One scenario, one repetition, in its own namespace."""
    # The arm is part of the namespace, or two arms run against the same cluster
    # collide on identical names and each tears down the other's stack.
    run_id = f"{arm_name}-{scenario.id.lower()}-{run_index}"
    started = time.monotonic()
    try:
        with EphemeralStack(run_id, context=context) as stack:
            injection = inject(scenario, stack)
            # Settle before reading: sampling mid-rollout reports the rollout
            # rather than the fault, and the arm would be deciding on noise.
            time.sleep(8)
            brief = brief_for(scenario, stack.observe())
            decision = build_arm(arm_name, stack).decide(brief)
            verdict = grade(scenario, decision.action, decision.escalated)
            return RunResult(
                scenario_id=scenario.id,
                arm=arm,
                run_index=run_index,
                verdict=verdict,
                action_taken=decision.action,
                escalated=decision.escalated,
                duration_seconds=round(time.monotonic() - started, 2),
                detail=f"{injection.describe} | {decision.rationale}",
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
