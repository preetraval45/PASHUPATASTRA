"""A model-agnostic diagnosis harness (RP-14).

The same harness must score an LLM and a Sati model identically, or the
comparison between them is unfair. So a diagnoser is anything with one method —
`diagnose(case) -> Diagnosis` — and everything else (which cases, which
options, how it is scored) is fixed here.

A **case** is evidence (each item with a ref), a closed option set, and the
correct label. Grading is identity on a string via `pashupatastra.diagnosis`,
never a model judging a model (rule 1).

What is reported, per diagnoser:

* **RCA@1 / RCA@3** — correct label first / in the top three, over all cases.
* **Precision when answering** — RCA@1 over the cases it did not abstain on.
* **Abstention rate** — "I can't tell" is allowed, and counted, not hidden.
* **Grounding** — share of answers whose cited refs all exist in the case.

Each with a Wilson interval. One JSONL line per answer, so a third party can
recompute every number.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from pashupatastra.diagnosis import wilson


@dataclass(frozen=True)
class Case:
    id: str
    evidence: tuple[tuple[str, str], ...]
    """(ref, content) pairs — what the diagnoser may read. Never the answer."""
    options: tuple[str, ...]
    correct: str


@dataclass(frozen=True)
class Diagnosis:
    ranked: tuple[str, ...] = ()
    """Labels, best first. Only the first three are scored."""
    abstain: bool = False
    evidence_refs: tuple[str, ...] = ()
    error: str = ""
    """Set when the diagnoser failed (provider down, invalid schema). Counted
    apart from wrong answers, as in adr/LLMBaselines."""


class Diagnoser(Protocol):
    name: str

    def diagnose(self, case: Case) -> Diagnosis: ...


@dataclass
class Scored:
    case: str
    diagnoser: str
    ranked: list[str]
    correct: str
    hit1: bool
    hit3: bool
    abstained: bool
    grounded: bool
    error: str = ""


@dataclass
class Report:
    diagnoser: str
    n: int
    answered: int
    rca1: float | None
    rca1_ci: tuple[float, float]
    rca3: float | None
    rca3_ci: tuple[float, float]
    precision_when_answering: float | None
    abstention_rate: float | None
    grounding: float | None
    errors: int
    rows: list[Scored] = field(default_factory=list)


def score(diagnoser: Diagnoser, cases: list[Case]) -> Report:
    rows: list[Scored] = []
    for case in cases:
        d = diagnoser.diagnose(case)
        top = [label.strip() for label in d.ranked[:3]]
        refs = {ref for ref, _ in case.evidence}
        answered = not d.abstain and not d.error and bool(top)
        rows.append(
            Scored(
                case=case.id,
                diagnoser=diagnoser.name,
                ranked=top,
                correct=case.correct,
                hit1=answered and top[0] == case.correct,
                hit3=answered and case.correct in top,
                abstained=d.abstain,
                grounded=answered and bool(d.evidence_refs) and set(d.evidence_refs) <= refs,
                error=d.error,
            )
        )

    n = len(rows)
    answered = [r for r in rows if not r.abstained and not r.error and r.ranked]
    hits1 = sum(r.hit1 for r in rows)
    hits3 = sum(r.hit3 for r in rows)
    return Report(
        diagnoser=diagnoser.name,
        n=n,
        answered=len(answered),
        rca1=hits1 / n if n else None,
        rca1_ci=wilson(hits1, n),
        rca3=hits3 / n if n else None,
        rca3_ci=wilson(hits3, n),
        precision_when_answering=(hits1 / len(answered)) if answered else None,
        abstention_rate=(sum(r.abstained for r in rows) / n) if n else None,
        grounding=(sum(r.grounded for r in answered) / len(answered)) if answered else None,
        errors=sum(bool(r.error) for r in rows),
        rows=rows,
    )


def write_jsonl(report: Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in report.rows:
            handle.write(json.dumps(asdict(row)) + "\n")


class StubRefused(RuntimeError):
    """The harness will not score the deterministic stub as if it were a model."""


def refuse_stub(model: str) -> None:
    if model in ("", "echo-0", "echo"):
        raise StubRefused(
            "the diagnoser is the deterministic stub; scoring it would report a "
            "fixture as a model result"
        )
