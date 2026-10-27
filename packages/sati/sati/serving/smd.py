"""Export Shailaputri, Siddhidatri and Mahagauri for serving, with incidents from servers they never saw.

    python -m sati.serving.smd --cache ../../.cache/smd --out ../../services/api/app/sati_models

All three read SMD (MIT): 28 real servers in three machine groups. They are
trained here on `machine-1` and `machine-2` exactly as evaluated, each by its
own module, and the incidents shipped for visitors come from `machine-3`, a
group none of them saw:

* **Shailaputri** (onset-weighted, as shown on the site) flags anomalous minutes.
* **Siddhidatri** fuses Shailaputri's score with two statistical scores into
  one calibrated probability; its weights come from out-of-fold scores.
* **Mahagauri** (out-of-fold threshold and hold, with the 3σ check, the
  variant within its safety budget) says when the incident is over.

The boosters are exported for `pashupatastra.trees`, and the export checks
that the served scores equal LightGBM's on every shipped minute. Shipped per
incident: the feature rows for its minutes, the labelled truth, and the
machine and minute range. No raw metric values are shipped.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from pashupatastra import trees

from sati.detect import model as detect_model
from sati.detect import smd as smd_run
from sati.fuse import run as fuse
from sati.sources import smd
from sati.verify import run as verify

HELD = "machine-3"
BEFORE = 30  # minutes shown before the incident starts
DEMO = 12  # incidents shipped


def exact(v) -> float | None:
    v = float(v)
    return None if math.isnan(v) else v


def rows(frame: pd.DataFrame, columns: list[str]) -> list[list[float | None]]:
    return [[exact(v) for v in r] for r in frame[columns].itertuples(index=False)]


def check(booster, served: dict, frame: pd.DataFrame) -> None:
    expected = booster.predict(frame[served["features"]])
    got = [trees.predict(served, r) for r in rows(frame, served["features"])]
    assert np.allclose(got, expected, atol=1e-9), "served scores differ from LightGBM"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--revision", default=smd_run.REVISION)
    args = parser.parse_args()

    machines = []
    for name in smd.MACHINES:
        m = smd.machine(name, args.cache, args.revision)
        m["features"] = smd_run.aggregate(m["train"], m["test"])
        m["pca"] = smd_run.pca_relative(m)
        machines.append(m)
    train = [m for m in machines if m["group"] != HELD]
    test = [m for m in machines if m["group"] == HELD]
    columns = list(train[0]["features"].columns)

    # Shailaputri: the onset-weighted detector, threshold chosen on the training groups.
    shail = smd_run.fit([m["features"] for m in train], [m["labels"] for m in train], onset=True)
    shail_t = smd_run.best(train, [shail.predict(m["features"]) for m in train], detect_model.THRESHOLDS)

    # Siddhidatri: logistic fusion on out-of-fold scores inside the training groups.
    oof_x, oof_y, oof_m, oof_s = [], [], [], []
    for g in sorted({m["group"] for m in train}):
        inner = fuse.fit([m for m in train if m["group"] != g])
        for m in (m for m in train if m["group"] == g):
            s = fuse.scores(m, inner, 0.999)
            oof_x.append(s)
            oof_y.append(m["labels"])
            oof_m.append(m)
            oof_s.append(s)
    weights = fuse.logistic(np.vstack(oof_x), np.concatenate(oof_y))
    fused_train = [fuse.predict(weights, s) for s in oof_s]
    fuse_t = smd_run.best(oof_m, fused_train, fuse.candidates(fused_train))
    plain = fuse.fit(train)

    # Mahagauri: out-of-fold threshold and hold, with the 3σ check.
    eps_train = [ep for m in train for ep in verify.episodes(m)]
    for ep in eps_train:
        ep["frame"], ep["y"] = verify.frame(ep), verify.labels(ep)
    maha = verify.fit(eps_train)
    within = [ep["frame"]["pre_beyond_3"].to_numpy() == 0 for ep in eps_train]
    maha_t, maha_hold = verify.choose_v2(eps_train, verify.out_of_fold(eps_train), agree=within)

    served = {
        "shailaputri": {**trees.compact(shail.dump_model(), columns), "threshold": shail_t},
        "siddhidatri_input": trees.compact(plain.dump_model(), columns),
        "siddhidatri": {"weights": [float(w) for w in weights], "threshold": float(fuse_t)},
    }
    maha_columns = list(eps_train[0]["frame"].columns)
    served["mahagauri"] = {**trees.compact(maha.dump_model(), maha_columns), "threshold": maha_t, "hold": maha_hold}

    # Incidents from the held-out group: their minutes, features and truth.
    demo = []
    for m in test:
        for ep in verify.episodes(m):
            ep["frame"], ep["y"] = verify.frame(ep), verify.labels(ep)
            lo = max(0, ep["start"] - BEFORE)
            window = m["features"].iloc[lo : ep["stop"]].reset_index(drop=True)
            check(shail, served["shailaputri"], window)
            check(plain, served["siddhidatri_input"], window)
            check(maha, served["mahagauri"], ep["frame"])
            extra = fuse.scores(m, plain, 0.999)[lo : ep["stop"], 1:]
            demo.append({
                "id": f"{m['name']}@{ep['start']}", "machine": m["name"],
                "minutes": ep["stop"] - lo, "incident": [ep["start"] - lo, ep["end"] - lo],
                "truth": [int(v) for v in m["labels"][lo : ep["stop"]]],
                "features": rows(window, columns),
                "statistical": [[exact(a), exact(b)] for a, b in extra],
                "verify": rows(ep["frame"], maha_columns),
            })
    demo.sort(key=lambda d: (-(d["incident"][1] - d["incident"][0]), d["id"]))
    demo = demo[:DEMO]

    out = {"models": served, "held_out_group": HELD,
           "trained_on": sorted({m["group"] for m in train}), "incidents": demo}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "smd.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    size = (args.out / "smd.json").stat().st_size / 1e6
    print(f"served SMD trio: {len(demo)} incidents from {HELD}; {size:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
