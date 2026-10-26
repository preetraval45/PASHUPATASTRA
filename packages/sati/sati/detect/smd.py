"""Shailaputri v1: multivariate anomaly detection on SMD, with whole machine groups held out.

    python -m sati.detect.smd --cache .cache/smd --out results/shailaputri-smd

**Features.** Shailaputri's causal per-series features (`features.py`) are
computed for each of a machine's 38 metrics over its whole history (the
unlabelled first half, then the test half). At each minute they are then
aggregated across metrics: the largest and the mean absolute deviation per
feature, and how many metrics deviate strongly. The model therefore reads "how
unusual is this server right now" in a form that means the same on any
machine, which is what a held-out group needs.

**Split.** Leave one machine group out. The model trains on the labelled test
halves of the other two groups, with its threshold chosen on those same
machines, and is tested on the held-out group's test halves. A machine's
unlabelled first half is used only as history for the causal features and as
the fitting data for the PCA baseline.

**Onset weighting** (the "earlier flags" item in RP-60). A variant gives the
first 20% of each labelled anomaly (at least 5 minutes) five times the training
weight, so the model is pushed to flag the start of an incident, not its
middle. It is measured as its own row; lead shows whether it helped.

**Baselines,** scored by the same online harness:

* **Max robust z:** the largest per-metric deviation from its hour-long
  baseline, thresholded. This is what a hand-set alert on every metric
  amounts to.
* **PCA per machine:** fitted on the machine's own unlabelled first half
  (reconstruction error, Lakhina et al. 2004). Its threshold is a quantile of
  the machine's own first-half scores, and the quantile is chosen on the
  training groups.

Scored event by event with `pashupatastra.evaluation.evaluate`: episode recall,
point precision, false alarms per 1000 minutes and lead. Never point-adjusted
F1, which inflates scores in this literature (datasheets.md).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from pashupatastra.evaluation import Series, evaluate

from sati.detect import features as feats
from sati.detect import model
from sati.loganomaly.run import pca_scores
from sati.sources import smd

REVISION = "7fb0e0acf89ea49908896bcc9f9e80fcfff6baf4"
METRICS = ("precision", "recall", "f1", "false_alarms_per_1000", "mean_lead")
STRONG = float(np.log1p(4.0))  # a compressed |z| above this is a raw deviation beyond 4
ONSET_SHARE, ONSET_MIN, ONSET_WEIGHT = 0.2, 5, 5.0
SCORE_QUANTILES = (0.9, 0.95, 0.98, 0.99, 0.995, 0.998, 0.999, 0.9995, 0.9999)
PCA_QUANTILES = (0.99, 0.995, 0.998, 0.999, 0.9995, 0.9999, 1.0)


def aggregate(train: np.ndarray, test: np.ndarray) -> pd.DataFrame:
    """Per-minute features for the test half, aggregated across the machine's metrics."""
    history = np.vstack([train, test])
    per_metric = [feats.features(history[:, j]).iloc[len(train):].reset_index(drop=True) for j in range(history.shape[1])]
    names = list(per_metric[0].columns)
    stacked = np.stack([f[names].to_numpy() for f in per_metric])  # metrics × minutes × features
    magnitude = np.abs(stacked)
    out = {}
    for k, name in enumerate(names):
        out[f"max_{name}"] = np.nanmax(magnitude[:, :, k], axis=0)
        out[f"mean_{name}"] = np.nanmean(magnitude[:, :, k], axis=0)
    for name in ("z_72", "z_diff"):
        k = names.index(name)
        out[f"strong_{name}"] = (magnitude[:, :, k] > STRONG).sum(axis=0).astype(float)
    return pd.DataFrame(out)


def onset_weights(labels: np.ndarray) -> np.ndarray:
    weights = np.ones(len(labels))
    for start, end in smd.ranges(labels):
        weights[start : start + max(ONSET_MIN, int((end - start) * ONSET_SHARE))] = ONSET_WEIGHT
    return weights


def fit(frames: list[pd.DataFrame], labels: list[np.ndarray], onset: bool) -> lgb.Booster:
    x = pd.concat(frames, ignore_index=True)
    y = np.concatenate(labels)
    w = np.concatenate([onset_weights(lab) for lab in labels]) if onset else None
    return lgb.train(model.PARAMS, lgb.Dataset(x, label=y, weight=w), num_boost_round=model.ROUNDS)


def score_rows(machines: list[dict], scores: list[np.ndarray], threshold: float, name: str) -> list[dict]:
    rows = []
    for m, s in zip(machines, scores, strict=True):
        replay = model.Replay(np.asarray(s, dtype=float), threshold)
        replay.name = name
        rows.append(evaluate(replay, Series(m["name"], list(m["test"][:, 0]), smd.ranges(m["labels"]))).row())
    return rows


def best(machines: list[dict], scores: list[np.ndarray], candidates) -> float:
    """The candidate threshold with the best mean F1 on these (training) machines."""
    return max(candidates, key=lambda t: np.mean([r["f1"] for r in score_rows(machines, scores, t, "x")]))


def zmax(m: dict) -> np.ndarray:
    """The max-robust-z baseline's score: the largest hour-baseline deviation across metrics."""
    return m["features"]["max_z_72"].fillna(0).to_numpy()


def mean(rows: list[dict]) -> dict[str, float]:
    return {k: round(float(np.mean([float(r[k]) for r in rows])), 3) for k in METRICS}


def pca_relative(m: dict) -> dict[float, np.ndarray]:
    """Test-half PCA scores divided by the machine's own first-half quantiles,
    so one threshold (a quantile choice) applies across machines."""
    train, test = m["train"], m["test"]
    fit_scores = pca_scores(train, train)
    test_scores = pca_scores(train, test)
    return {q: test_scores / max(np.quantile(fit_scores, q), 1e-12) for q in PCA_QUANTILES}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/smd"))
    parser.add_argument("--out", type=Path, default=Path("results/shailaputri-smd"))
    parser.add_argument("--revision", default=REVISION)
    parser.add_argument("--machines", type=int, default=len(smd.MACHINES), help="fewer for a smoke run")
    args = parser.parse_args()

    started = time.time()
    machines = []
    for name in smd.MACHINES[: args.machines]:
        m = smd.machine(name, args.cache, args.revision)
        m["features"] = aggregate(m["train"], m["test"])
        m["pca"] = pca_relative(m)
        machines.append(m)
        print(f"  {name}: {len(m['test'])} test minutes, {len(smd.ranges(m['labels']))} anomalies")
    groups = sorted({m["group"] for m in machines})

    folds = []
    for held in groups:
        train = [m for m in machines if m["group"] != held]
        test = [m for m in machines if m["group"] == held]
        if not train or not test:
            continue
        fold: dict[str, object] = {"held_out": held, "machines": len(test), "train_machines": len(train), "detectors": {}}
        for variant, onset in (("shailaputri-v1", False), ("shailaputri-v1 onset-weighted", True)):
            booster = fit([m["features"] for m in train], [m["labels"] for m in train], onset)
            t = best(train, [booster.predict(m["features"]) for m in train], model.THRESHOLDS)
            fold["detectors"][variant] = mean(score_rows(test, [booster.predict(m["features"]) for m in test], t, variant))
            fold.setdefault("thresholds", {})[variant] = t

        candidates = sorted({float(np.quantile(np.concatenate([zmax(m) for m in train]), q)) for q in SCORE_QUANTILES})
        t = best(train, [zmax(m) for m in train], candidates)
        fold["detectors"]["max robust z"] = mean(score_rows(test, [zmax(m) for m in test], t, "max robust z"))

        q = max(PCA_QUANTILES, key=lambda q: np.mean([r["f1"] for r in score_rows(train, [m["pca"][q] for m in train], 1.0, "x")]))
        fold["detectors"]["pca per machine"] = mean(score_rows(test, [m["pca"][q] for m in test], 1.0, "pca per machine"))
        fold.setdefault("thresholds", {})["pca quantile"] = q
        folds.append(fold)
        print(f"  held out {held}: " + "  ".join(f"{k} F1 {v['f1']:.3f}" for k, v in fold["detectors"].items()))

    names = list(folds[0]["detectors"]) if folds else []
    results = {
        "model": "sati-shailaputri-v1",
        "dataset": {"name": "SMD (Server Machine Dataset)", "repo": smd.REPO, "revision": args.revision,
                    "machines": len(machines), "groups": groups, "metrics_per_machine": int(machines[0]["test"].shape[1]),
                    "test_minutes": int(sum(len(m["test"]) for m in machines)),
                    "anomalies": int(sum(len(smd.ranges(m["labels"])) for m in machines))},
        "params": {"model": model.PARAMS, "rounds": model.ROUNDS, "onset": {"share": ONSET_SHARE, "min": ONSET_MIN,
                                                                             "weight": ONSET_WEIGHT}},
        "folds": folds,
        "mean_across_groups": {n: {k: round(float(np.mean([f["detectors"][n][k] for f in folds])), 3) for k in METRICS}
                               for n in names},
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
