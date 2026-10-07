"""Generate the evaluation page's contents by counting, not by claiming.

A venue review of the paper landed on 7 October 2026 and its verdict was that
the writing is publishable and the evaluation is not: too few scenarios run,
two arms with no data, no prompt-injection result, no outside users, and — the
one it called the biggest gap — **the language model is never tested**, because
the benchmark substitutes a deterministic stand-in for it.

The reflex is to fix the page before fixing the work. This script exists so
that cannot happen: every number on `/evaluation` is recounted here from the
corpus on disk, the harness's own declarations and the results directory, so
the page cannot say an arm has data when `benchmark/results/` is empty, and
cannot say diagnosis accuracy is measured while no run exists to measure. What
is missing renders as **absent with the reason**, the rule `/impact` is built
on, and the review's criticisms are published next to them rather than waited
out.

Imported rather than restated, so the page cannot drift from the harness:

* the corpus, via `pashupatastra.pib.load_corpus`
* what diagnosis can be scored on, via `pashupatastra.diagnosis`
* the arms, via `benchmark.harness.run.ARM_NAMES`
* the ablations, via `benchmark.harness.arms.Ablation`
* which faults cannot be injected and why, via `benchmark.harness.inject.UNSUPPORTED`

    python scripts/buildevaluation.py
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT))

from pashupatastra import diagnosis
from pashupatastra.pib import load_corpus, report

from benchmark.harness.arms import Ablation
from benchmark.harness.inject import UNSUPPORTED
from benchmark.harness.run import ARM_NAMES

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

OUT = ROOT / "apps" / "web" / "lib" / "evaluation.generated.json"
CORPUS = ROOT / "benchmark" / "incidents" / "pib"
RESULTS = ROOT / "benchmark" / "results"

#: The review, recorded as it was given. Each entry's `status` names what a
#: reader can go and check, or states plainly that nothing has closed it —
#: never "in progress", which is what a project says when it would rather not
#: answer. Dated, because a criticism answered later should be visibly answered
#: later rather than quietly edited away.
REVIEW_DATE = "2026-10-07"
REVIEW = [
    {
        "key": "thin",
        "finding": (
            "The evaluation is too thin: scenarios run once each, and two of the "
            "comparison arms have no data. The headline result — that a strict "
            "policy layer refused to act more often than a runbook did — is close "
            "to true by construction."
        ),
        "status": "open",
    },
    {
        "key": "model",
        "finding": (
            "The language model is never tested. The paper is about an AI agent, "
            "and the benchmark replaces the model with a deterministic stand-in, "
            "so nothing measures whether the diagnoses are correct. Called the "
            "biggest gap."
        ),
        "status": "instrument built, no run yet",
    },
    {
        "key": "injection",
        "finding": (
            "The design is argued to resist prompt injection and is never "
            "attacked. An AgentDojo-style test would turn the claim into a result."
        ),
        "status": "measured at the chat route",
    },
    {
        "key": "users",
        "finding": (
            "No outside users. The scenarios, the answer key and the system are "
            "all written by one person."
        ),
        "status": "open",
    },
    {
        "key": "novelty",
        "finding": (
            "Novelty is moderate. Policy gates, runbooks and safety shields exist "
            "already; the new part is combining them with citation-checked model "
            "reasoning, and that combination needs data behind it to stand as a "
            "contribution."
        ),
        "status": "open",
    },
]


def commit() -> str:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def runs_on_disk() -> dict[str, dict[str, object]]:
    """What the results directory actually holds, per arm.

    The whole point of reading this rather than being told: an arm the harness
    declares is not an arm that has been run. Repetitions are counted and
    reported separately from records, because the review's first finding is not
    that the corpus is small — it is that each scenario was run **once**, and a
    single run of a stochastic system is an anecdote with a decimal point.

    `exclusions*.jsonl` lines carry no `arm` and are skipped rather than
    counted as runs; they are the scenarios the harness refused, which belong
    to the injection section instead.
    """
    found: dict[str, dict[str, object]] = {}
    if not RESULTS.exists():
        return found
    for path in sorted(RESULTS.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            arm = record.get("arm")
            if not isinstance(arm, str):
                continue
            entry = found.setdefault(
                arm, {"records": 0, "scenarios": set(), "repeats": 0, "ablations": set()}
            )
            entry["records"] = int(entry["records"]) + 1  # type: ignore[call-overload]
            if isinstance(scenario := record.get("scenario_id"), str):
                entry["scenarios"].add(scenario)  # type: ignore[union-attr]
            if isinstance(index := record.get("run_index"), int):
                entry["repeats"] = max(int(entry["repeats"]), index + 1)
            if isinstance(ablation := record.get("ablation"), str):
                entry["ablations"].add(ablation)  # type: ignore[union-attr]
    return {
        arm: {
            "records": entry["records"],
            "scenarios": len(entry["scenarios"]),  # type: ignore[arg-type]
            "repeats": entry["repeats"],
            "ablations": sorted(entry["ablations"]),  # type: ignore[call-overload]
        }
        for arm, entry in found.items()
    }


def main() -> int:
    corpus = load_corpus(str(CORPUS))
    summary = report(corpus)
    scoreable = diagnosis.scoreable(corpus)
    options = diagnosis.labels(corpus)
    recorded = runs_on_disk()

    # Arms, each with its run count or the reason there is none. A declared arm
    # with zero runs is the review's first finding, stated here in the shape
    # that makes it unmissable rather than buried in a table of averages.
    arms = []
    for name in ARM_NAMES:
        entry = recorded.get(name)
        arms.append(
            {
                "name": name,
                "records": entry["records"] if entry else 0,
                "scenarios": entry["scenarios"] if entry else 0,
                "repeats": entry["repeats"] if entry else 0,
                "ablations": entry["ablations"] if entry else [],
                "absent": None
                if entry
                else (
                    "no run recorded here. The harness injects faults into a live "
                    "five-service Kubernetes stack, and no cluster has been stood "
                    "up for a scored run on this checkout"
                ),
            }
        )

    injectable = sorted({s.fault.type for s in corpus} - set(UNSUPPORTED))
    blocked = [
        {
            "fault": fault,
            "reason": reason,
            "scenarios": sum(1 for s in corpus if s.fault.type == fault),
        }
        for fault, reason in sorted(UNSUPPORTED.items())
    ]

    payload = {
        "note": (
            "Generated by scripts/buildevaluation.py. Every count here is "
            "recomputed from the corpus on disk, the harness's own declarations "
            "and benchmark/results/, so this page cannot report a measurement "
            "that was not taken."
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "commit": commit(),
        "corpus": {
            "scenarios": summary.total,
            "by_category": dict(sorted(summary.by_category.items())),
            "by_outcome": dict(sorted(summary.by_outcome.items())),
            "by_difficulty": dict(sorted(summary.by_difficulty.items())),
        },
        "diagnosis": {
            "scoreable": len(scoreable),
            "unscoreable": len(corpus) - len(scoreable),
            "unscoreable_reason": diagnosis.UNSCOREABLE["no_root_cause"],
            "options": len(options),
            "baseline": round(1 / len(options), 4) if options else None,
            "leakage": diagnosis.LEAKAGE,
            "graded_by": (
                "an identity comparison on a string. Grading a model with another "
                "model would break this project's first rule — the language model "
                "is never the source of truth — so diagnosis is posed as a closed "
                "choice over the corpus's own labels and a wrong answer is wrong "
                "in a way nobody can argue about."
            ),
            "measured": None,
            # Why there is no shortcut, which is the part a reader needs in
            # order to judge how much work closing this gap actually is.
            # Stated here rather than discovered: the obvious cheap version of
            # this experiment is invalid, and a number produced that way would
            # look like the missing result and would not be one.
            "no_shortcut": (
                "The scenario files cannot be used as the question. Each one "
                "names its own fault — PIB-0001 is titled \"Connection pool "
                "exhaustion via N+1 query deploy\" and its fault reads \"v4.21 "
                "introduces an N+1 query in the checkout path\" — so a model "
                "shown any of that is being asked to paraphrase an answer it "
                "has already been given. The legitimate input is the telemetry "
                "the fault produces once injected, which exists only while the "
                "stack is running. That is the whole reason this needs a "
                "cluster and not just a GPU."
            ),
            "absent": (
                "the grader exists and has never graded anything. Running it "
                "needs observable telemetry, which needs the five-service stack "
                "the faults are injected into, and no Kubernetes cluster is "
                "available on this checkout"
            ),
        },
        "arms": arms,
        "arms_declared": len(ARM_NAMES),
        "arms_with_data": sum(1 for arm in arms if arm["records"]),
        # Said out loud, because it is the reproducibility question a reviewer
        # asks first and the repository's own .gitignore is the answer.
        "records_are_tracked": False,
        "records_note": (
            "benchmark/results/ is gitignored, so the run records behind any "
            "table in the paper live on the machine that produced them and not "
            "in this repository. A reader cannot recompute a published number "
            "from here — only re-run the harness and compare. Publishing the "
            "records is a decision about size and about whether a run on one "
            "person's cluster is worth citing at all, and it has not been made."
        ),
        "ablations": [a.value for a in Ablation],
        "injection": {
            "injectable": injectable,
            "blocked": blocked,
            "blocked_scenarios": sum(entry["scenarios"] for entry in blocked),
        },
        "review": {"date": REVIEW_DATE, "findings": REVIEW},
    }

    OUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"corpus              {summary.total} scenarios, {len(summary.by_category)} categories")
    print(f"diagnosis scoreable {len(scoreable)} of {summary.total}, {len(options)}-way choice")
    print(f"                    baseline {1 / len(options):.1%}")
    for arm in arms:
        state = (
            f"{arm['records']} records over {arm['scenarios']} scenarios "
            f"x{arm['repeats']}"
            if arm["records"]
            else "no data"
        )
        print(f"  {arm['name']:16} {state}")
    print(f"faults blocked      {len(blocked)} types, {payload['injection']['blocked_scenarios']} scenarios")
    print(f"\nwrote {OUT.relative_to(ROOT)} at {payload['commit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
