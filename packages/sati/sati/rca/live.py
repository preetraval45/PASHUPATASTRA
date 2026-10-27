"""Sim-to-real on the live stack (RP-19): Katyayani on incidents from a real cluster.

    python -m sati.rca.live --data ../../benchmark/live/dataset --out ../../results/katyayani-live \
        [--rcaeval-cache ../../.cache/rcaeval]

The incidents are fault injections on an eight-service stack in kind
(`benchmark/live`): real processes, real CPU limits, real releases. Its metrics
are written in RCAEval's layout (`time`, `<service>_<metric>`), so the features
come from the same code (`sati.rca.features`) with no adapter of their own.

Ranked by, on the same incidents:

* **Katyayani trained on Kaal** (synthetic), zero-shot, on its Kaal features.
  Deploy-before is real here: a service whose ReplicaSet was created inside
  the incident window had a deploy, which Kubernetes records.
* **Katyayani trained on RCAEval** (real, other systems), zero-shot, on its own
  features. Only with `--rcaeval-cache`.
* the loudest service, and the earliest to go anomalous.

The answer (the plan's root) is joined on after the features are built, for
scoring only. Also written: the realism comparison RP-18 asked for, which
sets anomalous services per incident and propagation depth here beside Kaal's.
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from collections import Counter
from pathlib import Path

import pandas as pd
from pashupatastra.kaal.generator import callers_by_distance

from sati.rca import features as rfeat
from sati.rca import kaal, model
from sati.rca.simtoreal import kaal_features, train_kaal_ranker

METRICS = ("cpu", "mem", "latency-90", "request", "error")
KAAL_MANIFEST = Path(__file__).resolve().parents[4] / "docs" / "research" / "datasets" / "kaal-v1.json"


def frame_of(record: dict) -> pd.DataFrame:
    """The collector's lines → RCAEval's layout: `time` and one column per `<service>_<metric>`."""
    s = pd.DataFrame([x for x in record["samples"] if x.get("up")])
    wide = [s.pivot_table(index="t", columns="service", values=m).rename(columns=lambda c, m=m: f"{c}_{m}")
            for m in METRICS if m in s]
    return pd.concat(wide, axis=1).sort_index().reset_index().rename(columns={"t": "time"})


def features(record: dict, graph: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(RCAEval-style per-service features, Kaal-style features) for one incident. No label."""
    w = record["window"]
    window = rfeat.Window(before=w["before"], after=w["after"])
    table, _ = rfeat.incident_features(frame_of(record), record["inject_time"], window)
    table["case"] = record["id"]
    k = kaal_features(table, "live", graph)
    lo, hi = record["inject_time"] - w["before"], record["inject_time"] + w["after"]
    k["deploy_before"] = [int(any(lo <= t <= hi for t in record["deploys"].get(s, []))) for s in k["service"]]
    return table, k


def rcaeval_ranker(cache: Path):
    """Katyayani trained on every RCAEval RE1/RE2 case (all three systems)."""
    from sati.rca.run import TRAIN_SUITES, build
    from sati.sources import rcaeval

    subset = json.loads((Path(__file__).resolve().parents[4] / "benchmark/external/rcaeval/subset.json")
                        .read_text(encoding="utf-8"))
    rev = subset["revision"]
    index = rcaeval.cases(cache, rev)
    pool = index[index["suite"].isin(TRAIN_SUITES)]
    rcaeval.prefetch(list(pool["case"]), cache, rev)
    train, _ = build(pool, cache, rev)
    cols = rfeat.feature_columns(train.drop(columns=["suite"]))
    return model.train_ranker(train, cols), cols, int(pool["case"].nunique())


def depth(root: str, anomalous: set[str], calls: list) -> int:
    hops = dict(callers_by_distance(root, [tuple(c) for c in calls]))
    return max((hops.get(s, 0) for s in anomalous), default=0)


def shares(counts: dict) -> dict[str, float]:
    total = sum(counts.values())
    return {str(k): round(v / total, 4) for k, v in sorted(counts.items(), key=lambda kv: int(kv[0]))} if total else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("results/katyayani-live"))
    parser.add_argument("--rcaeval-cache", type=Path, default=None)
    parser.add_argument("--n", type=int, default=50_000, help="Kaal incidents to train on")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    started = time.time()

    meta = json.loads((args.data / "meta.json").read_text(encoding="utf-8"))
    graph = meta["graph"]
    with gzip.open(args.data / "incidents.jsonl.gz", "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    usable = [r for r in records if "error" not in r and r["samples"]]

    rf_parts, k_parts, roots, faults, sources = [], [], {}, {}, Counter()
    for r in usable:
        table, k = features(r, graph)
        if r["root"] not in set(k["service"]):
            continue
        rf_parts.append(table)
        k_parts.append(k)
        roots[r["id"]], faults[r["id"]] = r["root"], r["fault"]  # the answer, joined on for scoring only
        sources.update(x.get("source", "?") for x in r["samples"] if x.get("up"))
    rf, kf = pd.concat(rf_parts, ignore_index=True), pd.concat(k_parts, ignore_index=True)

    rankings = {
        "katyayani-kaal-v0 (trained on Kaal, zero-shot)": model.predict(train_kaal_ranker(args.n, args.seed), kf,
                                                                        kaal.FEATURES),
        "loudest service": model.rank(kf, kf["peak"].to_numpy()),
        "earliest anomaly": model.rank(kf, -kf["onset_rank"].fillna(1e9).to_numpy()),
    }
    rcaeval_cases = None
    if args.rcaeval_cache:
        booster, cols, rcaeval_cases = rcaeval_ranker(args.rcaeval_cache)
        for c in cols:
            if c not in rf:
                rf[c] = float("nan")  # a family this stack does not report
        rankings["katyayani (trained on RCAEval, zero-shot)"] = model.predict(booster, rf, cols)

    test = {}
    for name, ranked in rankings.items():
        row = {"rca@1": kaal.at_k(ranked, roots, 1), "rca@3": kaal.at_k(ranked, roots, 3), "by_fault": {}}
        for fault in sorted(set(faults.values())):
            part = {c: v for c, v in ranked.items() if faults[c] == fault}
            row["by_fault"][fault] = kaal.at_k(part, roots, 1)
        test[name] = row

    anomalous_counts, depths = Counter(), Counter()
    for case, g in kf.groupby("case"):
        hot = set(g.loc[g["peak"] >= kaal.ANOMALOUS, "service"])
        anomalous_counts[len(hot)] += 1
        depths[depth(roots[case], hot, graph["calls"])] += 1
    kaal_realism = json.loads(KAAL_MANIFEST.read_text(encoding="utf-8"))["realism"] if KAAL_MANIFEST.exists() else {}

    n_services = len(meta["services"])
    out = {
        "model": "sati-katyayani",
        "dataset": {"name": "live stack (RP-19)", "plan_sha256": meta["plan_sha256"], "planned": len(records),
                    "scored": len(roots), "errors": len(records) - len(usable),
                    "faults": dict(Counter(faults.values())), "services": n_services,
                    "metric_source": dict(sources)},
        "trained_on": {"kaal": {"n": args.n, "seed": args.seed}, "rcaeval_cases": rcaeval_cases},
        "chance": {"rca@1": round(1 / n_services, 4), "rca@3": round(3 / n_services, 4)},
        "test": test,
        "realism": {
            "anomalous_services_per_incident": {"live": shares(anomalous_counts),
                                                "kaal": shares(kaal_realism.get("anomalous_services_per_incident", {}))},
            "propagation_depth": {"live": shares(depths), "kaal": shares(kaal_realism.get("propagation_depth", {}))},
        },
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v["rca@1"]["value"] for k, v in test.items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
