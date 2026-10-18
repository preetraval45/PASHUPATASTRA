"""Score a diagnoser on the labelled incidents (RP-14).

    python scripts/benchdiagnosis.py --diagnoser llm:qwen2.5:7b
    python scripts/benchdiagnosis.py --diagnoser llm:mistral --runs 3

Cases are the labelled incidents in `benchmark/incidents/*.yaml` that carry a
closed answer key: `root_cause_label` and `options` (RP-13 adds them, answer
keys committed before any run). A fixture without a key is skipped and counted,
never guessed at — grading needs a label to compare, and inventing one here
would be this script writing its own answer key.

The diagnoser sees each signal as evidence with a ref (`sig-1`, …) and the
options, never the answer. LLM diagnosers go through the Gateway to the
baseline endpoint (`PASHU_BASELINE_*`, adr/LLMBaselines) and refuse the stub.
Results: one JSONL line per answer under `benchmark/results/diagnosis/`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT))

from benchmark.harness.diagnose import (  # noqa: E402
    Case,
    Diagnosis,
    refuse_stub,
    score,
    write_jsonl,
)

INSTRUCTIONS = """You diagnose the root cause of an incident from the evidence \
given. Choose from the listed options only, copying labels exactly. Rank up to \
three, most likely first. Cite the refs of the evidence your first choice rests \
on. If the evidence does not support a choice, abstain. Return JSON matching \
the schema."""


def load_cases(directory: Path) -> tuple[list[Case], list[str]]:
    cases, unkeyed = [], []
    for path in sorted(directory.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        label, options = doc.get("root_cause_label"), doc.get("options")
        if not label or not options:
            unkeyed.append(doc.get("id", path.stem))
            continue
        evidence = tuple(
            (f"sig-{i}", ", ".join(f"{k}={v}" for k, v in signal.items()))
            for i, signal in enumerate(doc.get("signals", []), start=1)
        )
        cases.append(Case(id=doc["id"], evidence=evidence, options=tuple(options), correct=label))
    return cases, unkeyed


class LLMDiagnoser:
    def __init__(self, model: str) -> None:
        from benchmark.harness.llm import baseline_gateway

        self.gateway = baseline_gateway(model)
        self.name = f"llm:{model}"
        refuse_stub(getattr(self.gateway.provider, "model", ""))

    def diagnose(self, case: Case) -> Diagnosis:
        from pashupatastra.gateway import Evidence, GatewayError, ModelRequest

        evidence = [Evidence(ref=ref, source="fixture", content=text, trusted=True) for ref, text in case.evidence]
        evidence.append(Evidence(ref="options", source="harness", content="\n".join(case.options), trusted=True))
        try:
            response = self.gateway.complete(
                ModelRequest(
                    purpose="diagnosis_benchmark",
                    instructions=INSTRUCTIONS,
                    question="Which option is the root cause? Options are in evidence ref 'options'.",
                    schema_name="diagnosis_v1",
                    evidence=evidence,
                    incident_id=case.id,
                    agent="baseline",
                    max_tokens=300,
                )
            )
        except GatewayError as error:
            return Diagnosis(error=str(error)[:200])
        out = response.output
        return Diagnosis(
            ranked=tuple(str(x) for x in out.get("ranked", []))[:3],
            abstain=bool(out.get("abstain")),
            evidence_refs=tuple(str(x) for x in out.get("evidence_refs", [])),
        )


def build(spec: str):
    kind, _, rest = spec.partition(":")
    if kind == "llm" and rest:
        return LLMDiagnoser(rest)
    if kind == "sati-rca":
        raise SystemExit(
            "sati-rca (Katyayani) ranks services from metric series; the labelled "
            "incidents carry event signals, not metric series, so it is scored on "
            "RCAEval instead (docs/research/models/sati-rca.md)."
        )
    raise SystemExit(f"unknown diagnoser {spec!r}; use llm:<model>")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diagnoser", required=True)
    parser.add_argument("--incidents", type=Path, default=ROOT / "benchmark" / "incidents")
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()

    cases, unkeyed = load_cases(args.incidents)
    print(f"{len(cases)} cases with an answer key; {len(unkeyed)} without ({', '.join(unkeyed) or 'none'})")
    if not cases:
        print("Nothing to score: the answer keys arrive with RP-13, committed before any run.")
        return 0

    diagnoser = build(args.diagnoser)
    out = ROOT / "benchmark" / "results" / "diagnosis"
    for run in range(1, args.runs + 1):
        report = score(diagnoser, cases)
        write_jsonl(report, out / f"{diagnoser.name.replace(':', '_')}-run{run}.jsonl")
        print(
            f"run {run}: RCA@1 {report.rca1:.3f} {report.rca1_ci}  RCA@3 {report.rca3:.3f}  "
            f"precision {report.precision_when_answering}  abstain {report.abstention_rate}  "
            f"grounded {report.grounding}  errors {report.errors}  n={report.n}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
