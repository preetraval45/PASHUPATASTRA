"""Train and test Sati-RCA v0 on RCAEval, end to end.

    python -m sati.rca.run --cache .cache/rcaeval --out results/sati-rca

Three ways of holding data out, each answering a different question:

* **leave-one-system-out** — trained on two systems, tested on the third. Can it
  diagnose a system it has never seen? This is the number that matters.
* **held-out fault type** — trained without one fault type, tested on it. Can it
  find the root cause of a kind of failure it never saw?
* **held-out repetition** — trained on earlier repetitions of every case, tested
  on the last. The in-distribution number; the gap to the two above is the
  generalisation gap, and it is reported rather than hidden.

RE3 (code-level faults, 90 cases) is never trained on. The final model, trained
on all of RE1 and RE2, is scored on it as a stress test.

Every split is scored for Sati-RCA and for the statistical baseline on exactly
the same incidents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import lightgbm as lgb
import pandas as pd

from sati.rca import features as feats
from sati.rca import model
from sati.rca.evaluate import score
from sati.sources import rcaeval

TRAIN_SUITES = ("RE1", "RE2")
STRESS_SUITE = "RE3"


def build(cases: pd.DataFrame, cache: Path, rev: str) -> tuple[pd.DataFrame, dict]:
    """The feature table for every case, and each case's provenance map."""
    rows, provenance, skipped = [], {}, []
    for case in cases.itertuples():
        frame = rcaeval.metrics(case.case, cache, rev)
        table, prov = feats.incident_features(frame, int(case.inject_time))
        if table.empty:
            skipped.append(case.case)
            continue
        table["case"] = case.case
        table["system"] = case.system
        table["dataset"] = case.dataset
        table["suite"] = case.suite
        table["fault"] = case.fault
        table["repetition"] = case.repetition
        table["root"] = case.root_cause_service
        table["label"] = (table["service"] == case.root_cause_service).astype(int)
        rows.append(table)
        provenance[case.case] = {f"{s}|{f}": c for (s, f), c in prov.items()}
    return pd.concat(rows, ignore_index=True), {"provenance": provenance, "skipped": skipped}


def splits(table: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    """(scheme, fold, test mask). Train is always the complement."""
    out = []
    for system in sorted(table["system"].unique()):
        out.append(("leave-one-system-out", system, table["system"] == system))
    for fault in sorted(table["fault"].unique()):
        out.append(("held-out-fault", fault, table["fault"] == fault))
    last = table.groupby(["dataset", "root", "fault"])["repetition"].transform("max")
    out.append(("held-out-repetition", "last", table["repetition"] == last))
    return out


def evaluate_fold(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> dict:
    # A case's rows must be all-train or all-test. Asserted, not assumed.
    assert not set(train["case"]) & set(test["case"]), "a case is on both sides of the split"
    booster = model.train_ranker(train, features)
    learned = model.predict(booster, test, features)
    stat = model.baseline(test)
    roots = test.groupby("case")["root"].first()
    return {
        "sati": [model.position(learned[c], r) for c, r in roots.items()],
        "baseline": [model.position(stat[c], r) for c, r in roots.items()],
        "cases": list(roots.index),
        "booster": booster,
        "learned": learned,
    }


def fault_head(train: pd.DataFrame, test: pd.DataFrame, learned: dict, features: list[str]) -> dict:
    """Fault type, end to end: trained on the true root's row, applied to the
    service Sati-RCA ranked first — so a wrong root is a wrong fault too."""
    classes = sorted(train["fault"].unique())
    if len(classes) < 2:
        return {}
    booster = model.train_fault(train[train["label"] == 1], features, classes)
    correct = total = 0
    for case, ranking in learned.items():
        rows = test[(test["case"] == case) & (test["service"] == ranking[0])]
        truth = test[test["case"] == case]["fault"].iloc[0]
        if truth not in classes or rows.empty:
            continue
        guess = classes[int(booster.predict(rows[features]).argmax(axis=1)[0])]
        correct += int(guess == truth)
        total += 1
    return {"fault_accuracy": round(correct / total, 4) if total else None, "fault_n": total}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/rcaeval"))
    parser.add_argument("--out", type=Path, default=Path("results/sati-rca"))
    parser.add_argument("--revision", default=None, help="dataset commit; default: current")
    parser.add_argument("--limit", type=int, default=0, help="cases per dataset (smoke runs)")
    args = parser.parse_args()

    started = time.time()
    rev = args.revision or rcaeval.revision()
    index = rcaeval.cases(args.cache, rev)
    if args.limit:
        index = index.groupby("dataset", group_keys=False).head(args.limit)
    print(f"RCAEval @ {rev[:12]} — {len(index)} cases")

    rcaeval.prefetch(list(index["case"]), args.cache, rev)
    table, extra = build(index, args.cache, rev)
    features = feats.feature_columns(table.drop(columns=["suite"]))

    missing_root = (table.groupby("case")["label"].sum() == 0).sum()
    train_pool = table[table["suite"].isin(TRAIN_SUITES)]
    stress = table[table["suite"] == STRESS_SUITE]

    results: dict[str, object] = {
        "model": "sati-rca-v0",
        "dataset": {"name": "RCAEval", "repo": rcaeval.REPO, "revision": rev,
                    "cases": int(index["case"].nunique()),
                    "train_suites": list(TRAIN_SUITES), "stress_suite": STRESS_SUITE},
        "root_not_among_candidates": int(missing_root),
        "skipped_cases": extra["skipped"],
        "features": features,
        "params": {"ranker": model.RANKER_PARAMS, "rounds": model.RANKER_ROUNDS},
        "splits": [],
    }

    pooled: dict[str, dict[str, list]] = {}
    for scheme, fold, mask in splits(train_pool):
        train, test = train_pool[~mask], train_pool[mask]
        if test.empty or train.empty:
            continue
        fold_result = evaluate_fold(train, test, features)
        entry = {
            "scheme": scheme,
            "fold": fold,
            "train_cases": int(train["case"].nunique()),
            "sati": score(fold_result["sati"]),
            "baseline": score(fold_result["baseline"]),
        }
        if scheme == "leave-one-system-out":
            entry.update(fault_head(train, test, fold_result["learned"], features))
        results["splits"].append(entry)
        bucket = pooled.setdefault(scheme, {"sati": [], "baseline": []})
        bucket["sati"] += fold_result["sati"]
        bucket["baseline"] += fold_result["baseline"]
        print(f"  {scheme:22} {fold:16} sati AC@1 {entry['sati']['ac@1']:.3f}  baseline {entry['baseline']['ac@1']:.3f}  n={entry['sati']['n']}")

    results["pooled"] = {
        scheme: {"sati": score(b["sati"]), "baseline": score(b["baseline"])} for scheme, b in pooled.items()
    }

    # Ablation. `n_series` counts a service's metrics, and in RCAEval the root
    # cause is always an application service, never a database — which tend to
    # carry fewer series. A model can lean on that prior without diagnosing
    # anything, so leave-one-system-out is re-run without it and both are
    # reported. The gap is how much of the score is "which kind of service".
    lean = [f for f in features if f != "n_series"]
    ablated: list[int | None] = []
    for scheme, _fold, mask in splits(train_pool):
        if scheme != "leave-one-system-out":
            continue
        ablated += evaluate_fold(train_pool[~mask], train_pool[mask], lean)["sati"]
    results["ablation_no_n_series"] = {"scheme": "leave-one-system-out", "sati": score(ablated)}

    # The model that serves: trained on everything in RE1 and RE2.
    final = model.train_ranker(train_pool, features)
    if not stress.empty:
        learned = model.predict(final, stress, features)
        stat = model.baseline(stress)
        roots = stress.groupby("case")["root"].first()
        results["stress_re3"] = {
            "sati": score([model.position(learned[c], r) for c, r in roots.items()]),
            "baseline": score([model.position(stat[c], r) for c, r in roots.items()]),
        }

    args.out.mkdir(parents=True, exist_ok=True)
    model_path = args.out / "sati-rca-v0.txt"
    final.save_model(str(model_path))
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    meta = {
        "model": "sati-rca-v0",
        "sha256": digest,
        "features": features,
        "trained_on": {"suites": list(TRAIN_SUITES), "cases": int(train_pool["case"].nunique()),
                       "dataset_revision": rev},
        "lightgbm": lgb.__version__,
        "python": platform.python_version(),
    }
    (args.out / "sati-rca-v0.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # One worked explanation, so the citation path is exercised on real data.
    sample = train_pool[train_pool["label"] == 1].iloc[[0]]
    case = str(sample["case"].iloc[0])
    prov = {tuple(k.split("|", 1)): v for k, v in extra["provenance"][case].items()}
    results["example_explanation"] = {
        "case": case,
        "service": str(sample["service"].iloc[0]),
        "reasons": model.explain(final, sample, features, prov),
    }
    results["model_sha256"] = digest
    results["seconds"] = round(time.time() - started, 1)
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"done in {results['seconds']}s — model {digest[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
