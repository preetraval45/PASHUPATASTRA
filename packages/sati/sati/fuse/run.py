"""Train and test Siddhidatri v0: three detectors fused into one calibrated verdict.

    python -m sati.fuse.run --cache .cache/smd --out results/siddhidatri

Siddhidatri is model 9 of the nine (adr/Navadurga): the one that combines the
others. On SMD's 28 real servers, three detectors each score every minute:

* **Shailaputri v1:** the learned detector (`sati.detect.smd`).
* **Max robust z:** the largest per-metric deviation, what per-metric alerts
  amount to.
* **PCA per machine:** reconstruction error against the machine's own first
  half.

Siddhidatri is a logistic regression over the three scores. Its output is a
**probability**, and it is held to that: of the minutes it calls 80% likely
anomalous, about 80% should be. Fusion that is only a better ranking would be
a fourth detector, not a verdict.

**No leakage in the stacking.** Inside the two training groups, Shailaputri
is trained on one group and scores the other (out of fold). The fusion
weights are learned on those out-of-fold scores, never on a model's scores on
its own training data. The held-out group is then scored by a Shailaputri
trained on both training groups.

**Measured:**

* **Calibration:** expected calibration error (ECE, 10 bins) and Brier score
  per minute, against the same detector's raw score passed through a sigmoid
  of its own.
* **Detection:** event-level F1, recall and false alarms per 1000, through
  the same harness as every detector. The threshold is chosen on the training
  groups.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np

from sati.detect import model as detect_model
from sati.detect import smd as smd_run
from sati.sources import smd

FEATURES = ("shailaputri", "max robust z", "pca")


def logistic(x: np.ndarray, y: np.ndarray, steps: int = 400, l2: float = 1e-3) -> np.ndarray:
    """Weights (bias last) for P(y=1|x), by Newton's method with a small ridge."""
    a = np.hstack([x, np.ones((len(x), 1))])
    w = np.zeros(a.shape[1])
    for _ in range(steps):
        p = 1 / (1 + np.exp(-np.clip(a @ w, -30, 30)))
        grad = a.T @ (p - y) + l2 * w
        hess = (a * (p * (1 - p))[:, None]).T @ a + l2 * np.eye(len(w))
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(np.hstack([x, np.ones((len(x), 1))]) @ w, -30, 30)))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error: the bin-weighted gap between stated and observed rates."""
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if mask.any():
            total += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return round(float(total), 4)


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return round(float(np.mean((p - y) ** 2)), 4)


def scores(m: dict, booster: lgb.Booster, pca_q: float) -> np.ndarray:
    """The three detector scores per minute, transformed to a comparable scale."""
    return np.column_stack([
        booster.predict(m["features"]),
        np.log1p(smd_run.zmax(m)),
        np.log1p(np.clip(m["pca"][pca_q], 0, None)),
    ])


def fit(machines: list[dict]) -> lgb.Booster:
    return smd_run.fit([m["features"] for m in machines], [m["labels"] for m in machines], onset=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/smd"))
    parser.add_argument("--out", type=Path, default=Path("results/siddhidatri"))
    parser.add_argument("--revision", default=smd_run.REVISION)
    parser.add_argument("--machines", type=int, default=len(smd.MACHINES))
    args = parser.parse_args()

    started = time.time()
    machines = []
    for name in smd.MACHINES[: args.machines]:
        m = smd.machine(name, args.cache, args.revision)
        m["features"] = smd_run.aggregate(m["train"], m["test"])
        m["pca"] = smd_run.pca_relative(m)
        machines.append(m)
    groups = sorted({m["group"] for m in machines})
    pca_q = 0.999

    folds = []
    for held in groups:
        train = [m for m in machines if m["group"] != held]
        test = [m for m in machines if m["group"] == held]
        inner = sorted({m["group"] for m in train})
        if not test or len(inner) < 2:
            continue
        # Out-of-fold Shailaputri scores inside the training groups.
        oof_x, oof_y, oof_machines, oof_scores = [], [], [], []
        for g in inner:
            booster = fit([m for m in train if m["group"] != g])
            for m in (m for m in train if m["group"] == g):
                s = scores(m, booster, pca_q)
                oof_x.append(s)
                oof_y.append(m["labels"])
                oof_machines.append(m)
                oof_scores.append(s)
        x, y = np.vstack(oof_x), np.concatenate(oof_y)
        fused_w = logistic(x, y)
        single_w = {name: logistic(x[:, [k]], y) for k, name in enumerate(FEATURES)}

        # Thresholds on the training groups' out-of-fold probabilities.
        fused_train = [predict(fused_w, s) for s in oof_scores]
        t_fused = smd_run.best(oof_machines, fused_train, detect_model.THRESHOLDS)
        t_single = {name: smd_run.best(oof_machines, [predict(single_w[name], s[:, [k]]) for s in oof_scores],
                                       detect_model.THRESHOLDS) for k, name in enumerate(FEATURES)}

        booster = fit(train)
        test_scores = [scores(m, booster, pca_q) for m in test]
        y_test = np.concatenate([m["labels"] for m in test])
        detectors = {}
        p_fused = [predict(fused_w, s) for s in test_scores]
        detectors["siddhidatri-v0"] = {
            **smd_run.mean(smd_run.score_rows(test, p_fused, t_fused, "siddhidatri-v0")),
            "ece": ece(np.concatenate(p_fused), y_test), "brier": brier(np.concatenate(p_fused), y_test)}
        for k, name in enumerate(FEATURES):
            p = [predict(single_w[name], s[:, [k]]) for s in test_scores]
            detectors[name] = {**smd_run.mean(smd_run.score_rows(test, p, t_single[name], name)),
                               "ece": ece(np.concatenate(p), y_test), "brier": brier(np.concatenate(p), y_test)}
        folds.append({"held_out": held, "machines": len(test), "weights": dict(zip([*FEATURES, "bias"],
                                                                                  map(float, np.round(fused_w, 4)), strict=True)),
                      "thresholds": {"siddhidatri-v0": t_fused, **t_single}, "detectors": detectors})
        print(f"  held out {held}: " + "  ".join(f"{k} F1 {v['f1']:.3f} ECE {v['ece']:.3f}" for k, v in detectors.items()))

    names = list(folds[0]["detectors"]) if folds else []
    keys = (*smd_run.METRICS, "ece", "brier")
    results = {
        "model": "sati-siddhidatri-v0",
        "dataset": {"name": "SMD (Server Machine Dataset)", "repo": smd.REPO, "revision": args.revision,
                    "machines": len(machines), "groups": groups},
        "fused": list(FEATURES),
        "folds": folds,
        "mean_across_groups": {n: {k: round(float(np.mean([f["detectors"][n][k] for f in folds])), 4) for k in keys}
                               for n in names},
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

