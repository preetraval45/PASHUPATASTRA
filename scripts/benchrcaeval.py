"""Diagnose RCAEval cases with any diagnoser, scored by the RP-14 harness (RP-33).

    python scripts/benchrcaeval.py --diagnoser llm:llama3 --cache .cache/rcaeval
    python scripts/benchrcaeval.py --diagnoser sati-kaal --cache .cache/rcaeval
    python scripts/benchrcaeval.py --diagnoser loudest --cache .cache/rcaeval
    python scripts/benchrcaeval.py --diagnoser katyayani --cache .cache/rcaeval

Cases are the **pre-declared LLM sample** in `benchmark/external/rcaeval/subset.json`
(`llm_sample`: 50 Online Boutique and 50 Sock Shop cases, chosen by hash before
any run). Each case becomes harness evidence: one line per service, built by
the RP-32 adapter from the metrics and the authored call graph (peak deviation,
onset order, metric families moved, own-resource signal, callers and callees),
never the label. The options are the case's candidate services.

Every diagnoser is scored by the same harness (`benchmark.harness.diagnose.score`):
RCA@1, RCA@3, abstention, grounding and errors, with Wilson intervals. So an LLM
and Sati are compared on identical evidence, cases and grading. LLMs go through
the Gateway to the baseline endpoint (adr/LLMBaselines) and refuse the stub.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark.harness.diagnose import Case, Diagnosis, score, write_jsonl  # noqa: E402

SUBSET = ROOT / "benchmark" / "external" / "rcaeval" / "subset.json"


def sample() -> tuple[str, list[str]]:
    subset = json.loads(SUBSET.read_text(encoding="utf-8"))
    s = subset["llm_sample"]
    if hashlib.sha256("\n".join(s["cases"]).encode()).hexdigest() != s["cases_sha256"]:
        raise SystemExit("llm_sample no longer matches its declared hash")
    return subset["revision"], s["cases"]


def describe(row) -> str:
    onset = "none" if row["onset_rank"] != row["onset_rank"] else f"#{int(row['onset_rank'])} (+{row['onset_min']:.1f} min)"
    return (f"service={row['service']}; peak deviation={row['peak']:.1f} sigma; first anomalous={onset}; "
            f"metric families moved={int(row['n_anomalous'])}; own resource metric moved={'yes' if row['own_metric'] else 'no'}; "
            f"calls {int(row['out_degree'])} services ({int(row['anomalous_callees'])} anomalous); "
            f"called by {int(row['in_degree'])} ({int(row['anomalous_callers'])} anomalous)")


def build_cases(cache: Path) -> tuple[list[Case], dict]:
    from sati.rca import external
    from sati.sources import rcaeval

    rev, names = sample()
    index = rcaeval.cases(cache, rev)
    index = index[index["case"].isin(set(names))]
    rcaeval.prefetch(list(index["case"]), cache, rev)
    cases, tables = [], {}
    for _, row in index.iterrows():
        inputs = external.inputs(row, cache, rev)
        answer = external.answer(row)
        if answer not in set(inputs["service"]):
            continue
        tables[str(row["case"])] = inputs
        evidence = tuple((f"svc-{i}", describe(r)) for i, (_, r) in enumerate(inputs.iterrows(), start=1))
        cases.append(Case(id=str(row["case"]), evidence=evidence, options=tuple(inputs["service"]), correct=answer))
    return cases, tables


class Ranked:
    """A diagnoser that ranks services by a score column (no learning, or Sati's ranker)."""

    def __init__(self, name: str, tables: dict, scorer) -> None:
        self.name, self.tables, self.scorer = name, tables, scorer

    def diagnose(self, case: Case) -> Diagnosis:
        t = self.tables[case.id]
        order = t.assign(score=self.scorer(t)).sort_values(["score", "service"], ascending=[False, True])
        ranked = tuple(order["service"])[:3]
        top = ranked[0]
        refs = tuple(ref for ref, text in case.evidence if text.startswith(f"service={top};"))
        return Diagnosis(ranked=ranked, evidence_refs=refs)


class Katyayani:
    """Katyayani trained on real RCAEval incidents from the *other* systems
    (RE1 and RE2, Train Ticket included), leave one system out, on its own
    features (`sati.rca.features`). The like-for-like row: same cases, same
    harness, trained on real data instead of Kaal."""

    name = "katyayani"

    def __init__(self, cache: Path) -> None:
        from sati.rca import features as rfeat
        from sati.rca import model as rmodel
        from sati.rca.run import TRAIN_SUITES, build as build_table
        from sati.sources import rcaeval

        rev, names = sample()
        index = rcaeval.cases(cache, rev)
        pool = index[index["suite"].isin(TRAIN_SUITES) & ~index["case"].isin(set(names))]
        test = index[index["case"].isin(set(names))]
        rcaeval.prefetch(list(pool["case"]) + list(test["case"]), cache, rev)
        train_table, _ = build_table(pool, cache, rev)
        test_table, _ = build_table(test, cache, rev)
        features = rfeat.feature_columns(train_table.drop(columns=["suite"]))
        self.rankings: dict[str, list[str]] = {}
        for system in sorted(test_table["system"].unique()):
            ranker = rmodel.train_ranker(train_table[train_table["system"] != system], features)
            part = test_table[test_table["system"] == system]
            self.rankings.update(rmodel.predict(ranker, part, features))

    def diagnose(self, case: Case) -> Diagnosis:
        ranked = tuple(self.rankings.get(case.id, []))[:3]
        if not ranked:
            return Diagnosis(error="no features for this case")
        refs = tuple(ref for ref, text in case.evidence if text.startswith(f"service={ranked[0]};"))
        return Diagnosis(ranked=ranked, evidence_refs=refs)


def build(spec: str, tables: dict, cache: Path):
    kind, _, rest = spec.partition(":")
    if kind == "llm" and rest:
        from benchdiagnosis import LLMDiagnoser

        return LLMDiagnoser(rest)
    if kind == "loudest":
        return Ranked("loudest", tables, lambda t: t["peak"].to_numpy())
    if kind == "katyayani":
        return Katyayani(cache)
    if kind == "sati-kaal":
        from sati.rca import kaal
        from sati.rca.simtoreal import train_kaal_ranker

        ranker = train_kaal_ranker(50_000, 1)
        return Ranked("sati-kaal", tables, lambda t: ranker.predict(t[kaal.FEATURES]))
    raise SystemExit(f"unknown diagnoser {spec!r}; use llm:<model>, katyayani, sati-kaal or loudest")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diagnoser", required=True)
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "rcaeval")
    parser.add_argument("--out", type=Path, default=ROOT / "benchmark" / "results" / "rcaeval")
    args = parser.parse_args()

    cases, tables = build_cases(args.cache)
    print(f"{len(cases)} RCAEval cases from the declared LLM sample")
    diagnoser = build(args.diagnoser, tables, args.cache)
    report = score(diagnoser, cases)
    write_jsonl(report, args.out / f"{diagnoser.name.replace(':', '_')}.jsonl")
    print(f"{diagnoser.name}: RCA@1 {report.rca1:.3f} {report.rca1_ci}  RCA@3 {report.rca3:.3f}  "
          f"abstain {report.abstention_rate}  grounded {report.grounding}  errors {report.errors}  n={report.n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
