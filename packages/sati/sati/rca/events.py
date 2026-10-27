"""Can the real-data Katyayani be served from what the API holds?

    python -m sati.rca.events --cache ../../.cache/rcaeval --live ../../benchmark/live/dataset \
        --out ../../results/katyayani-events

The strong Katyayani (`sati-rca.md`) reads raw metric time series. The API's
incidents hold events instead: a metric's deviation in σ, its onset, deploys
and logs, which is what `sati.rca.kaal.featurise` turns into features. So the
ranker that can be served is one trained on *real* incidents expressed in
those event-level features. `simtoreal.kaal_features` already maps a real
case into them.

Three systems with known call graphs: RCAEval's Online Boutique and Sock Shop
(the pinned subset), and the live stack (RP-19). Each is held out in turn and
ranked by:

* **events, real-trained:** LightGBM on the other two systems' real cases, in
  event features. This is the candidate for serving.
* **events, Kaal-trained:** the same features, trained on 50,000 synthetic
  incidents (`simtoreal.train_kaal_ranker`), as served today.
* **loudest service:** the no-learning rule.

`deploy_before` is set to 0 everywhere. RCAEval records no deploys, and on the
live stack only the release fault deploys, so the feature would identify the
fault rather than diagnose it (RP-12 notes, L2).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from sati.rca import external, kaal, model
from sati.rca.simtoreal import train_kaal_ranker
from sati.sources import rcaeval

SUBSET = Path(__file__).resolve().parents[4] / "benchmark" / "external" / "rcaeval" / "subset.json"


def rcaeval_rows(cache: Path) -> pd.DataFrame:
    subset = external.load_subset(SUBSET)
    rev = subset["revision"]
    index = rcaeval.cases(cache, rev)
    index = index[index["case"].isin(set(subset["cases"]))]
    rcaeval.prefetch(list(index["case"]), cache, rev)
    parts = []
    for _, case in index.iterrows():
        rows = external.inputs(case, cache, rev)
        answer = external.answer(case)  # joined on after the adapter, for scoring only
        if answer in set(rows["service"]):
            parts.append(rows.assign(system=case["system"], label=(rows["service"] == answer).astype(int)))
    return pd.concat(parts, ignore_index=True)


def live_rows(data: Path) -> pd.DataFrame:
    import gzip

    from sati.rca.live import features

    meta = json.loads((data / "meta.json").read_text(encoding="utf-8"))
    with gzip.open(data / "incidents.jsonl.gz", "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    parts = []
    for r in records:
        if "error" in r or not r["samples"]:
            continue
        _, k = features(r, meta["graph"])
        if r["root"] in set(k["service"]):
            parts.append(k.assign(system="live", label=(k["service"] == r["root"]).astype(int)))
    return pd.concat(parts, ignore_index=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("results/katyayani-events"))
    parser.add_argument("--n", type=int, default=50_000)
    args = parser.parse_args()
    started = time.time()

    table = pd.concat([rcaeval_rows(args.cache), live_rows(args.live)], ignore_index=True)
    table["deploy_before"] = 0
    synthetic = train_kaal_ranker(args.n, 1)

    results = {}
    for held in sorted(table["system"].unique()):
        test, train = table[table["system"] == held], table[table["system"] != held]
        roots = {c: g.loc[g["label"] == 1, "service"].iloc[0] for c, g in test.groupby("case")}
        real = model.predict(model.train_ranker(train, kaal.FEATURES), test, kaal.FEATURES)
        results[held] = {
            "cases": len(roots),
            "train_systems": sorted(train["system"].unique()),
            "events, real-trained": kaal.at_k(real, roots, 1),
            "events, Kaal-trained": kaal.at_k(model.predict(synthetic, test, kaal.FEATURES), roots, 1),
            "loudest service": kaal.at_k(model.rank(test, test["peak"].to_numpy()), roots, 1),
        }
        print(held, {k: v["value"] for k, v in results[held].items() if isinstance(v, dict)})

    out = {"model": "sati-katyayani-events", "features": kaal.FEATURES, "deploy_before": "zeroed",
           "kaal_training": {"n": args.n, "seed": 1}, "systems": results,
           "seconds": round(time.time() - started, 1)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
