"""Sim-to-real for RP-24: train on Kaal (synthetic), test zero-shot on RCAEval (real).

    python -m sati.rca.simtoreal --cache .cache/rcaeval --out results/katyayani-simtoreal

The Kaal-trained ranker (`sati.rca.kaal`) has never seen a real incident. Here
it ranks the services of real fault-injection cases from RCAEval, with no
training on them. Its per-service features are rebuilt from each case's
metrics (`sati.rca.features`) and from the system's call graph.

**Call graphs are authored, then checked against traces.** RCAEval ships metrics, not
topology. The graphs below are written from each project's published
architecture: Google's microservices-demo README for Online Boutique, and
Weaveworks' Sock Shop design for Sock Shop. Train Ticket (64 components) is
**excluded**, because a hand-written graph of it would be a guess. Each run checks
the authored graph against the edges in one traced case (`graph_check`). Sock
Shop has no traces in RCAEval, so its graph stays unchecked, and the results
say so.

**Feature mapping**, Kaal → RCAEval:

* peak σ is the case's largest robust shift, uncompressed.
* onset and its rank come from the first threshold crossing.
* the count of anomalous metrics is the number of metric families that moved.
* own resource metric means CPU, memory or "other" moved.
* deploy-before and error-log are 0: RCAEval has no deploy events, and its
  logs are not used here.
* layer, degrees, and anomalous callees and callers come from the authored
  graph.

**Compared with,** on the same cases: the loudest service, the earliest to go
anomalous, and Katyayani trained on RCAEval itself (leave-one-system-out, from
its own results file; reported, not re-run).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pashupatastra.kaal.dataset import assign
from pashupatastra.kaal.generator import incident
from pashupatastra.kaal.references import REFERENCES

from sati.rca import features as rfeat
from sati.rca import kaal, model
from sati.sources import rcaeval

# One copy of the authored graphs, shared with the RP-18 contamination guard.
GRAPHS = REFERENCES
RESOURCE_FAMILIES = ("cpu", "mem", "other")


def kaal_features(table: pd.DataFrame, system: str) -> pd.DataFrame:
    """RCAEval per-service features → the Kaal ranker's feature columns."""
    graph = GRAPHS[system]
    calls = graph["calls"]
    callees: dict[str, list[str]] = {}
    callers: dict[str, list[str]] = {}
    for a, b in calls:  # type: ignore[union-attr]
        callees.setdefault(a, []).append(b)
        callers.setdefault(b, []).append(a)
    peak = np.expm1(table["peak_any"].fillna(0).clip(lower=0))
    anomalous_mask = peak >= kaal.ANOMALOUS
    anomalous = set(table.loc[anomalous_mask, "service"])
    onset = table["onset_any"].where(anomalous_mask)
    first = onset.min()
    out = pd.DataFrame({
        "case": table["case"], "service": table["service"], "label": table["label"],
        "onset_min": (onset - first) / 60.0,
        "onset_rank": onset.rank(method="first"),
        "peak": peak,
        "n_anomalous": table["families_moved"].fillna(0),
        "own_metric": (table[[f"shift_{f}" for f in RESOURCE_FAMILIES]].abs() > np.log1p(3)).any(axis=1).astype(int),
        "deploy_before": 0, "error_log": 0,
    })
    out["in_degree"] = [len(callers.get(s, [])) for s in table["service"]]
    out["out_degree"] = [len(callees.get(s, [])) for s in table["service"]]
    out["anomalous_callees"] = [sum(c in anomalous for c in callees.get(s, [])) for s in table["service"]]
    out["anomalous_callers"] = [sum(c in anomalous for c in callers.get(s, [])) for s in table["service"]]
    out["callee_share"] = [out.loc[i, "anomalous_callees"] / d if (d := out.loc[i, "out_degree"]) else 0.0 for i in out.index]
    out["caller_share"] = [out.loc[i, "anomalous_callers"] / d if (d := out.loc[i, "in_degree"]) else 0.0 for i in out.index]
    layer = graph["layer"]
    for x in kaal.LAYERS:
        out[f"layer_{x}"] = [int(layer.get(s, "backend") == x) for s in table["service"]]  # type: ignore[union-attr]
    return out


def trace_edges(case: str, cache: Path, rev: str) -> set[tuple[str, str]]:
    """Caller → callee pairs observed in one case's traces: a span whose parent
    belongs to a different service. Used to check an authored graph."""
    t = pd.read_parquet(rcaeval.fetch(f"{case}/traces.parquet", cache, rev), columns=["spanID", "parentSpanID", "serviceName"])
    service = dict(zip(t["spanID"], t["serviceName"], strict=True))
    norm = {"frontendservice": "frontend"}
    return {(norm.get(service[p], service[p]), norm.get(s, s))
            for p, s in zip(t["parentSpanID"], t["serviceName"], strict=True)
            if p in service and service[p] != s}


def graph_check(system: str, index: pd.DataFrame, cache: Path, rev: str) -> dict:
    """Authored edges against traced ones, on the first case of the system with traces."""
    traced = index[(index["system"] == system) & index["has_traces"]]
    if traced.empty:
        return {"checked": False, "why": "RCAEval has no traces for this system"}
    observed = trace_edges(str(traced.iloc[0]["case"]), cache, rev)
    authored = {tuple(e) for e in GRAPHS[system]["calls"]}  # type: ignore[union-attr]
    return {"checked": True, "case": str(traced.iloc[0]["case"]),
            "observed_edges": len(observed), "observed_and_authored": len(observed & authored),
            "observed_not_authored": sorted(map(list, observed - authored)),
            "authored_not_observed": sorted(map(list, authored - observed))}


def train_kaal_ranker(n: int, seed: int):
    splits = assign(n, seed)
    frames = []
    for i in range(n):
        inc = incident(seed, i)
        if splits[inc.id] == "train" and inc.label["root_service"] is not None:
            frames.append(kaal.featurise(inc)[0])
    return model.train_ranker(pd.concat(frames, ignore_index=True), kaal.FEATURES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/rcaeval"))
    parser.add_argument("--out", type=Path, default=Path("results/katyayani-simtoreal"))
    parser.add_argument("--n", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="cases per system, for a smoke run; 0 means all")
    parser.add_argument("--katyayani", type=Path, default=Path("../../docs/research/models/sati-rca.results.json"))
    args = parser.parse_args()

    started = time.time()
    ranker = train_kaal_ranker(args.n, args.seed)
    rev = rcaeval.revision()
    index = rcaeval.cases(args.cache, rev)
    index = index[index["system"].isin(GRAPHS)]
    checks = {s: graph_check(s, index, args.cache, rev) for s in GRAPHS}  # on every case, before any --limit
    if args.limit:
        index = index.groupby("system", group_keys=False).head(args.limit)
    rcaeval.prefetch(list(index["case"]), args.cache, rev)

    tables = {s: [] for s in GRAPHS}
    for _, case in index.iterrows():
        frame = rcaeval.metrics(case["case"], args.cache, rev)
        table, _ = rfeat.incident_features(frame, int(case["inject_time"]))
        if case["root_cause_service"] not in set(table["service"]):
            continue
        table["case"] = case["case"]
        table["label"] = (table["service"] == case["root_cause_service"]).astype(int)
        tables[case["system"]].append(kaal_features(table, case["system"]))

    results = {}
    for system, parts in tables.items():
        f = pd.concat(parts, ignore_index=True)
        roots = {c: g.loc[g["label"] == 1, "service"].iloc[0] for c, g in f.groupby("case")}
        rankings = {
            "katyayani-kaal-v0 (zero-shot)": model.predict(ranker, f, kaal.FEATURES),
            "loudest service": model.rank(f, f["peak"].to_numpy()),
            "earliest anomaly": model.rank(f, -f["onset_rank"].fillna(1e9).to_numpy()),
        }
        results[system] = {name: {"rca@1": kaal.at_k(r, roots, 1), "rca@3": kaal.at_k(r, roots, 3)}
                           for name, r in rankings.items()}
        print(system, {k: v["rca@1"]["value"] for k, v in results[system].items()})

    reference = None
    if args.katyayani.exists():
        reference = {"source": str(args.katyayani.name),
                     "note": "Katyayani trained on RCAEval (leave-one-system-out); see sati-rca.md for its per-system rows"}
    out = {
        "model": "sati-katyayani-kaal-v0",
        "trained_on": {"dataset": "Kaal v1", "n": args.n, "seed": args.seed},
        "tested_on": {"dataset": "RCAEval", "revision": rev, "systems": list(GRAPHS),
                      "cases": {s: int(pd.concat(p)["case"].nunique()) for s, p in tables.items() if p},
                      "excluded": {"tt": "Train Ticket: no call graph authored (64 components)"}},
        "graphs": {s: {"calls": [list(c) for c in g["calls"]],
                       "source": "authored from the project's published architecture",
                       "trace_check": checks[s]}
                   for s, g in GRAPHS.items()},
        "test": results,
        "reference": reference,
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
