"""Export Katyayani for serving in the API, with incidents it never saw to try it on.

    python -m sati.rca.serve --cache ../../.cache/rcaeval --live ../../benchmark/live/dataset \
        --out ../../services/api/app/sati_models

The served model is the event-feature Katyayani (`sati.rca.events`): trained on
real incidents from RCAEval's Online Boutique and Sock Shop and from the live
stack, in the features the API can compute. One in ten incidents, chosen by a
hash of its id, is **reserved**: kept out of training and shipped as the cases
a visitor can run the model on. So every answer shown on the site is on an
incident the model never trained on, and its truth is shown beside it.

The booster is exported as JSON for `pashupatastra.trees` (plain Python, no
LightGBM in the Lambda). The export checks that it ranks every reserved case
exactly as LightGBM does before writing. RCAEval is MIT-licensed; the live
stack's incidents are this project's own.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd
from pashupatastra import trees

from sati.rca import kaal, model
from sati.rca.events import live_rows, rcaeval_rows

SYSTEMS = {"ob": "Online Boutique", "ss": "Sock Shop", "live": "Live test cluster"}
SHOWN = ("peak", "onset_rank", "n_anomalous", "anomalous_callees", "anomalous_callers")


def reserved(case: str) -> bool:
    return int(hashlib.sha256(case.encode()).hexdigest()[:8], 16) % 10 == 0


def exact(v: float) -> float | None:
    """Full precision: a rounded value can cross a split threshold."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def shown(v: float) -> float | None:
    return None if exact(v) is None else round(float(v), 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    table = pd.concat([rcaeval_rows(args.cache), live_rows(args.live)], ignore_index=True)
    table["deploy_before"] = 0  # RCAEval records no deploys; see sati.rca.events
    held = table["case"].map(reserved)
    train, demo = table[~held], table[held]
    booster = model.train_ranker(train, kaal.FEATURES)
    served = trees.compact(booster.dump_model(), kaal.FEATURES)

    cases, hits = [], 0
    for case, g in demo.groupby("case", sort=True):
        rows = g.to_dict("records")
        expected = booster.predict(g[kaal.FEATURES])
        got = [trees.predict(served, [exact(r[f]) for f in kaal.FEATURES]) for r in rows]
        # Scores, not orders: two services can tie, and ties may sort either way.
        assert all(abs(a - b) < 1e-6 for a, b in zip(got, expected, strict=True)), f"{case}: served scores differ"
        scores = dict(zip((r["service"] for r in rows), got, strict=True))
        mine = sorted(scores, key=lambda s: -scores[s])
        root = g.loc[g["label"] == 1, "service"].iloc[0]
        hits += mine[0] == root
        cases.append({
            "id": case, "system": SYSTEMS.get(g["system"].iloc[0], g["system"].iloc[0]), "root": root,
            "services": [{"name": r["service"], "features": {f: exact(r[f]) for f in kaal.FEATURES},
                          "shown": {f: shown(r[f]) for f in SHOWN}} for r in rows],
        })

    out = {
        "model": "katyayani", "features": kaal.FEATURES, "booster": served,
        "trained_on": {"incidents": int(train["case"].nunique()),
                       "systems": sorted(SYSTEMS[s] for s in train["system"].unique()),
                       "by_system": {SYSTEMS[k]: int(v) for k, v in train.groupby("system")["case"].nunique().items()}},
        "reserved": {"incidents": len(cases), "rca@1": round(hits / len(cases), 4) if cases else None},
        "cases": cases,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "katyayani.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"served Katyayani: trained on {out['trained_on']['incidents']} incidents; "
          f"{len(cases)} reserved, RCA@1 {out['reserved']['rca@1']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
