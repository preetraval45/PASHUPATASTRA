"""Katyayani v1: does real data from one more system help on the others?

    python -m sati.rca.pooled --cache ../../.cache/rcaeval --live ../../benchmark/live/dataset \
        --out ../../results/katyayani-pooled

Four systems with real fault injections: RCAEval's Online Boutique, Sock Shop
and Train Ticket (RE1 and RE2), and the live stack (RP-19, 200 incidents).
Each is held out in turn, and on it two rankers are compared on exactly the
same cases:

* **v0:** trained on the other RCAEval systems only, as in `sati-rca.md`;
* **v1:** trained on the other systems *including* the live stack.

The only difference is the live training data, so the paired McNemar test on
RCA@1 says whether it helped. The live stack held out is the zero-shot result
already in `katyayani-live.md`, re-run here on the same features for
reference. Features come from `sati.rca.features` for every system, so no
system gets a feature the others lack (the live stack's `deploy_before` is not
used).
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path

import pandas as pd
from pashupatastra.significance import mcnemar

from sati.rca import features as rfeat
from sati.rca import kaal, model
from sati.rca.live import features as live_features
from sati.rca.run import TRAIN_SUITES, build
from sati.sources import rcaeval

SUBSET = Path(__file__).resolve().parents[4] / "benchmark" / "external" / "rcaeval" / "subset.json"


def live_table(data: Path) -> pd.DataFrame:
    meta = json.loads((data / "meta.json").read_text(encoding="utf-8"))
    with gzip.open(data / "incidents.jsonl.gz", "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    parts = []
    for r in records:
        if "error" in r or not r["samples"]:
            continue
        table, _ = live_features(r, meta["graph"])
        if r["root"] not in set(table["service"]):
            continue
        parts.append(table.assign(system="live", fault=r["fault"], root=r["root"],
                                  label=(table["service"] == r["root"]).astype(int)))
    return pd.concat(parts, ignore_index=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("results/katyayani-pooled"))
    args = parser.parse_args()
    started = time.time()

    rev = json.loads(SUBSET.read_text(encoding="utf-8"))["revision"]
    index = rcaeval.cases(args.cache, rev)
    pool = index[index["suite"].isin(TRAIN_SUITES)]
    rcaeval.prefetch(list(pool["case"]), args.cache, rev)
    real, _ = build(pool, args.cache, rev)
    table = pd.concat([real.drop(columns=["suite", "dataset", "repetition"], errors="ignore"), live_table(args.live)],
                      ignore_index=True)
    features = rfeat.feature_columns(table)
    for c in features:
        table[c] = pd.to_numeric(table[c], errors="coerce")

    results = {}
    for held in sorted(table["system"].unique()):
        test = table[table["system"] == held]
        roots = test.groupby("case")["root"].first().to_dict()
        others = table[table["system"] != held]
        v0 = model.predict(model.train_ranker(others[others["system"] != "live"], features), test, features)
        row = {"cases": len(roots), "v0 (other RCAEval systems)": kaal.at_k(v0, roots, 1)}
        if held != "live":
            v1 = model.predict(model.train_ranker(others, features), test, features)
            row["v1 (+ live stack)"] = kaal.at_k(v1, roots, 1)
            t = mcnemar([(v1[c][0] == r, v0[c][0] == r) for c, r in roots.items()])
            row["paired"] = {"only_v1": t.only_a, "only_v0": t.only_b, "p": t.p_value}
        row["loudest"] = kaal.at_k(model.baseline(test), roots, 1)
        results[held] = row
        print(held, {k: v["value"] for k, v in row.items() if isinstance(v, dict) and "value" in v})

    out = {"model": "sati-katyayani-v1", "rcaeval_revision": rev, "train_suites": list(TRAIN_SUITES),
           "systems": results, "features": len(features), "seconds": round(time.time() - started, 1)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
