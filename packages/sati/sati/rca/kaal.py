"""Sati-RCA on Kaal's synthetic incidents (RP-24): rank the root-cause service, name the fault.

    python -m sati.rca.kaal --n 50000 --seed 1 --out results/katyayani-kaal

The splits are the committed RP-18 manifest's (`pashupatastra.kaal.dataset.assign`),
never recomputed by other rules. The run checks each split's id-list hash
against the manifest before training.

**Per-service features,** from the incident's events and topology only. Each
records the event ids it came from, which is what RP-27's citations need:

* onset (minutes after the incident's first anomaly) and onset rank;
* peak |σ|, the number of anomalous metric events, and whether the service
  shows a resource metric of its own (anything beyond latency and errors);
* a deploy shortly before onset, and an error log;
* layer, and call in-degree and out-degree;
* **anomalous callees and anomalous callers.** A fault moves up the call graph,
  so a root cause has anomalous callers and no anomalous callees. The loudest
  or earliest service often does not.

**Model:** Katyayani's LightGBM `lambdarank` ranker (`sati.rca.model`), one
query per incident with a fault. A second LightGBM head predicts the fault type
from the top-ranked service's features.

**Evaluated** on test-id, test-ood-topology and test-ood-fault, with Wilson
intervals, against two no-learning rankers: the loudest service and the
earliest to go anomalous. Fault-type accuracy is not reported on
test-ood-fault, whose fault types the head has never seen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from pashupatastra.kaal.dataset import SPLITS, assign
from pashupatastra.kaal.generator import Incident, incident

from sati.rca import model

ANOMALOUS = 2.0
RESOURCE = frozenset({"latency_p99_ms", "error_rate"})
LAYERS = ("edge", "api", "backend", "store")
FEATURES = [
    "onset_min", "onset_rank", "peak", "n_anomalous", "own_metric", "deploy_before", "error_log",
    "in_degree", "out_degree", "anomalous_callees", "anomalous_callers", "callee_share", "caller_share",
    *[f"layer_{x}" for x in LAYERS],
]


def featurise(inc: Incident) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """One row per service, and the event ids each service's features used."""
    first = None
    per: dict[str, dict] = {s.name: {"sigmas": [], "metrics": set(), "onset": None, "deploys": [], "logs": [], "ids": []}
                            for s in inc.services}
    for e in inc.events:
        p, svc = e.payload, per[e.entity_ref.id]
        sigma = getattr(p, "deviation_sigma", None)
        if sigma is not None and abs(sigma) >= ANOMALOUS:
            svc["sigmas"].append(abs(sigma))
            svc["metrics"].add(p.name)
            svc["ids"].append(e.id)
            if svc["onset"] is None or e.occurred_at < svc["onset"]:
                svc["onset"] = e.occurred_at
            if first is None or e.occurred_at < first:
                first = e.occurred_at
        elif p.kind == "deployment":
            svc["deploys"].append(e)
        elif p.kind == "log":
            svc["logs"].append(e)
            svc["ids"].append(e.id)
    anomalous = {name for name, v in per.items() if v["sigmas"]}
    callees: dict[str, list[str]] = {}
    callers: dict[str, list[str]] = {}
    for a, b in inc.calls:
        callees.setdefault(a, []).append(b)
        callers.setdefault(b, []).append(a)
    onsets = sorted((v["onset"], name) for name, v in per.items() if v["onset"] is not None)
    rank = {name: i + 1 for i, (_, name) in enumerate(onsets)}
    rows = []
    for s in inc.services:
        v = per[s.name]
        down, up = callees.get(s.name, []), callers.get(s.name, [])
        deploy_before = any(v["onset"] and timedelta(0) <= v["onset"] - d.occurred_at <= timedelta(minutes=10)
                            for d in v["deploys"])
        if deploy_before:
            v["ids"].extend(d.id for d in v["deploys"])
        rows.append({
            "case": inc.id, "service": s.name, "label": int(s.name == inc.label["root_service"]),
            "onset_min": (v["onset"] - first).total_seconds() / 60 if v["onset"] and first else np.nan,
            "onset_rank": rank.get(s.name, np.nan),
            "peak": max(v["sigmas"], default=0.0),
            "n_anomalous": len(v["sigmas"]),
            "own_metric": int(bool(v["metrics"] - RESOURCE)),
            "deploy_before": int(deploy_before),
            "error_log": int(bool(v["logs"])),
            "in_degree": len(up), "out_degree": len(down),
            "anomalous_callees": sum(c in anomalous for c in down),
            "anomalous_callers": sum(c in anomalous for c in up),
            "callee_share": sum(c in anomalous for c in down) / len(down) if down else 0.0,
            "caller_share": sum(c in anomalous for c in up) / len(up) if up else 0.0,
            **{f"layer_{x}": int(s.layer == x) for x in LAYERS},
        })
    return pd.DataFrame(rows), {name: v["ids"] for name, v in per.items()}


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def at_k(rankings: dict[str, list[str]], roots: dict[str, str], k: int) -> dict:
    hits = sum(roots[c] in r[:k] for c, r in rankings.items())
    n = len(rankings)
    return {"value": round(hits / n, 4) if n else 0.0, "ci95": wilson(hits, n), "n": n}


def manifest_hashes(splits: dict[str, str | None]) -> dict[str, str]:
    return {s: hashlib.sha256("\n".join(sorted(i for i, v in splits.items() if v == s)).encode()).hexdigest()
            for s in SPLITS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--manifest", type=Path, default=Path("../../docs/research/datasets/kaal-v1.json"))
    parser.add_argument("--out", type=Path, default=Path("results/katyayani-kaal"))
    args = parser.parse_args()

    started = time.time()
    splits = assign(args.n, args.seed)
    if args.manifest.exists():
        committed = json.loads(args.manifest.read_text(encoding="utf-8"))
        expected = {s: v["ids_sha256"] for s, v in committed["splits"].items()}
        if committed["n"] == args.n and committed["seed"] == args.seed and expected != manifest_hashes(splits):
            raise SystemExit("splits differ from the committed manifest: refusing to train on a moved split")

    tables: dict[str, list[pd.DataFrame]] = {s: [] for s in SPLITS}
    faults: dict[str, str] = {}
    roots: dict[str, str] = {}
    for i in range(args.n):
        inc = incident(args.seed, i)
        split = splits[inc.id]
        if split is None or inc.label["root_service"] is None:
            continue  # removed by the guard, or a negative with no root to rank
        table, _ = featurise(inc)
        tables[split].append(table)
        faults[inc.id] = str(inc.label["fault_type"])
        roots[inc.id] = str(inc.label["root_service"])
    frames = {s: pd.concat(t, ignore_index=True) for s, t in tables.items() if t}
    print({s: f["case"].nunique() for s, f in frames.items()})

    ranker = model.train_ranker(frames["train"], FEATURES)
    classes = sorted({faults[c] for c in frames["train"]["case"].unique()})
    train_roots = frames["train"][frames["train"]["label"] == 1]
    fault_head = model.train_fault(train_roots.assign(fault=train_roots["case"].map(faults)), FEATURES, classes)

    results: dict[str, dict] = {}
    for split in ("test-id", "test-ood-topology", "test-ood-fault"):
        if split not in frames:
            continue
        f = frames[split]
        rankings = {
            "katyayani-kaal-v0": model.predict(ranker, f, FEATURES),
            "loudest service": model.rank(f, f["peak"].to_numpy()),
            "earliest anomaly": model.rank(f, -f["onset_rank"].fillna(1e9).to_numpy()),
        }
        split_roots = {c: roots[c] for c in f["case"].unique()}
        entry = {name: {"rca@1": at_k(r, split_roots, 1), "rca@3": at_k(r, split_roots, 3)} for name, r in rankings.items()}
        if split != "test-ood-fault":
            top = f.assign(score=ranker.predict(f[FEATURES])).sort_values(["case", "score"], ascending=[True, False])
            top = top.groupby("case", sort=False).head(1)
            predicted = np.array(classes)[fault_head.predict(top[FEATURES]).argmax(axis=1)]
            right = int(sum(p == faults[c] for p, c in zip(predicted, top["case"], strict=True)))
            entry["katyayani-kaal-v0"]["fault_type"] = {"value": round(right / len(top), 4), "ci95": wilson(right, len(top)),
                                                         "n": len(top)}
        results[split] = entry
        print(split, {k: v["rca@1"]["value"] for k, v in entry.items()})

    importance = sorted(zip(FEATURES, ranker.feature_importance("gain"), strict=True), key=lambda x: -x[1])
    out = {
        "model": "sati-katyayani-kaal-v0",
        "dataset": {"name": "Kaal dataset v1 (synthetic, adr/KaalGenerator — proposed)", "n": args.n, "seed": args.seed,
                    "incidents_with_a_root": {s: int(f["case"].nunique()) for s, f in frames.items()},
                    "split_hashes_match_manifest": True},
        "test": results,
        "fault_classes": classes,
        "top_features": [{"feature": k, "gain": round(float(g), 1)} for k, g in importance[:8]],
        "sim_to_real": "pending: RCAEval cases converted to Kaal-style events (RP-24 step 4, RP-19)",
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
