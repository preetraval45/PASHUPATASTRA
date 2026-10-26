"""Train and test Chandraghanta v0: network intrusion detection on UNSW-NB15 and CIC-IDS2017.

    python -m sati.netdetect.run --unsw <folder> --cic <folder> --out results/chandraghanta

Chandraghanta is model 3 of the nine (adr/Navadurga): the guard at the gate,
reading network flows. It is a LightGBM classifier over each flow's features.
Its threshold is chosen on a validation slice of the training data only.

**UNSW-NB15** uses its official training and testing files. The variant
without TTL fields measures how much of the score comes from TTL values, which
nearly identify the testbed's attack traffic.

**CIC-IDS2017** is split by day: trained on Monday to Wednesday (benign
traffic, brute force, DoS, Heartbleed) and tested on Thursday and Friday (web
attacks, infiltration, botnet, port scan, DDoS). Every test attack family is
one the model never saw. For contrast, a random split of all days is also
reported. It is the setting most published results use, and it is not the
claim.

**Baseline:** PCA reconstruction error, fitted on benign training flows only
(Lakhina et al., SIGCOMM 2004). It needs no attack labels, so unseen families
are not unseen to it in the way they are to a classifier.

Reported per dataset: precision, recall, F1 and false-positive rate on benign
flows, plus recall for each attack family. Weights are not published, because
both datasets are research-use only (datasheets.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from sati.loganomaly.run import metrics, pca_scores
from sati.sources import netflow

PARAMS: dict[str, object] = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbosity": -1,
    "seed": 7,
    "deterministic": True,
    "force_row_wise": True,
    # `deterministic` holds only for a fixed thread count; runners vary, and on
    # 26 Oct the same code and data gave four different Shailaputri models.
    "num_threads": 2,
}
ROUNDS = 300
VALIDATION = 0.2
PCA_SAMPLE = 200_000


def validation_mask(n: int, salt: str) -> np.ndarray:
    """A deterministic VALIDATION share of rows, by hash of the row's position."""
    return np.array([int(hashlib.sha256(f"{salt}:{i}".encode()).hexdigest()[:8], 16) % 1000 < VALIDATION * 1000
                     for i in range(n)])


def threshold(y: np.ndarray, scores: np.ndarray) -> float:
    """The F1-best threshold on validation, over the whole score range."""
    candidates = np.unique(np.quantile(scores, np.linspace(0.01, 0.999, 300)))
    return float(max(candidates, key=lambda t: metrics(y, (scores >= t).astype(int))["f1"]))


def signed_log(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.log1p(np.abs(x))


def fit_lgb(x: pd.DataFrame, y: np.ndarray) -> lgb.Booster:
    weight = float((y == 0).sum() / max(1, (y == 1).sum()))
    return lgb.train({**PARAMS, "scale_pos_weight": weight}, lgb.Dataset(x, label=y), num_boost_round=ROUNDS)


def detect(xtr: pd.DataFrame, ytr: np.ndarray, xte: pd.DataFrame, salt: str) -> tuple[np.ndarray, float]:
    """Train on the training rows outside the validation slice, choose the
    threshold on the slice, and return 0/1 flags for the test rows."""
    val = validation_mask(len(xtr), salt)
    booster = fit_lgb(xtr[~val], ytr[~val])
    t = threshold(ytr[val], booster.predict(xtr[val]))
    return (booster.predict(xte) >= t).astype(int), t


def pca_detect(xtr: pd.DataFrame, ytr: np.ndarray, xte: pd.DataFrame, salt: str) -> np.ndarray:
    medians = xtr.median()
    a, b = (signed_log(f.fillna(medians).to_numpy(dtype=float)) for f in (xtr, xte))
    val = validation_mask(len(a), salt)
    benign = a[~val & (ytr == 0)]
    if len(benign) > PCA_SAMPLE:
        benign = benign[np.random.default_rng(7).choice(len(benign), PCA_SAMPLE, replace=False)]
    t = threshold(ytr[val], pca_scores(benign, a[val]))
    return (pca_scores(benign, b) >= t).astype(int)


def per_family(families: pd.Series, flags: dict[str, np.ndarray], seen: set[str]) -> dict[str, dict]:
    out = {}
    for family in sorted(families.unique()):
        rows = (families == family).to_numpy()
        attack = family not in ("Normal", "BENIGN")
        entry: dict[str, object] = {"n": int(rows.sum()), "attack": attack, "seen_in_training": family in seen}
        for name, flag in flags.items():
            # Recall for an attack family; for benign, the share wrongly flagged.
            entry[name] = round(float(flag[rows].mean()), 4)
        out[family] = entry
    return out


def run_unsw(folder: Path) -> dict:
    data = netflow.unsw(folder)
    train, test = data["train"], data["test"]
    ytr, yte = train["label"].to_numpy(), test["label"].to_numpy()
    xtr, xte = netflow.unsw_features(train, test)
    xtr_nt, xte_nt = netflow.unsw_features(train, test, drop_ttl=True)
    flags = {
        "chandraghanta-v0": detect(xtr, ytr, xte, "unsw")[0],
        "chandraghanta-v0 without TTL": detect(xtr_nt, ytr, xte_nt, "unsw")[0],
        "pca (benign-only)": pca_detect(xtr, ytr, xte, "unsw"),
    }
    return {
        "name": "UNSW-NB15",
        "split": "official training and testing files",
        "files": data["files"],
        "rows": {"train": len(train), "test": len(test)},
        "attack_share_test": round(float(yte.mean()), 4),
        "detectors": {name: metrics(yte, flag) for name, flag in flags.items()},
        "per_family": per_family(test["family"], flags, set(train["family"])),
    }


def run_cic(folder: Path) -> dict:
    data = netflow.cic(folder)
    features = netflow.cic_features(data)
    is_train = data["day"].isin(("Monday", "Tuesday", "Wednesday")).to_numpy()
    train, test = data[is_train].reset_index(drop=True), data[~is_train].reset_index(drop=True)
    ytr, yte = train["label"].to_numpy(), test["label"].to_numpy()
    flags = {
        "chandraghanta-v0": detect(train[features], ytr, test[features], "cic")[0],
        "pca (benign-only)": pca_detect(train[features], ytr, test[features], "cic"),
    }

    # The setting most published results use: a random split of all days.
    held = validation_mask(len(data), "cic-random")
    y_all = data["label"].to_numpy()
    random_flags, _ = detect(data.loc[~held, features].reset_index(drop=True), y_all[~held],
                             data.loc[held, features].reset_index(drop=True), "cic-random-val")
    return {
        "name": "CIC-IDS2017",
        "split": "by day: trained on Monday to Wednesday, tested on Thursday and Friday",
        "rows": {"train": len(train), "test": len(test)},
        "days": {"train": ["Monday", "Tuesday", "Wednesday"], "test": ["Thursday", "Friday"]},
        "attack_share_test": round(float(yte.mean()), 4),
        "detectors": {name: metrics(yte, flag) for name, flag in flags.items()},
        "per_family": per_family(test["family"], flags, set(train["family"])),
        "reference_random_split": {"rows_test": int(held.sum()), "chandraghanta-v0": metrics(y_all[held], random_flags)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--unsw", type=Path, required=True, help="folder holding the UNSW-NB15 CSVs")
    parser.add_argument("--cic", type=Path, required=True, help="folder holding the CIC-IDS2017 CSVs")
    parser.add_argument("--out", type=Path, default=Path("results/chandraghanta"))
    args = parser.parse_args()

    started = time.time()
    results = {
        "model": "sati-chandraghanta-v0",
        "datasets": {"unsw": run_unsw(args.unsw), "cic": run_cic(args.cic)},
        "weights_published": False,
        "weights_note": "UNSW-NB15 and CIC-IDS2017 are research-use only; weights are withheld pending the owner's decision.",
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for key, d in results["datasets"].items():
        for name, m in d["detectors"].items():
            print(f"  {key:5} {name:30} P {m['precision']:.3f} R {m['recall']:.3f} F1 {m['f1']:.3f} FPR {m['false_positive_rate']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
