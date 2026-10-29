"""Train and test Kalaratri v0 — log anomaly detection on LogHub HDFS.

    python -m sati.loganomaly.run --cache .cache/loghub --out results/kalaratri
    python -m sati.loganomaly.run --dataset bgl --cache .cache/loghub-bgl --out results/kalaratri-bgl

HDFS is grouped by block. BGL has no blocks, so it is cut into fixed windows of
100 consecutive lines (`loghub.bgl_windows`). Everything after that is shared.

**Split by time, never at random.** Blocks are taken in the order the log
produced them: the first 60% train, the next 20% choose the threshold, the last
20% test. Random splits — common in published HDFS results — let a model see
later log templates and later failure modes during training, which is leakage
(Kapoor & Narayanan 2023) and is why many reported HDFS F1s near 0.99 do not
survive deployment.

The model: per block, counts of each log template (vocabulary from training
blocks only, plus an "unseen template" count), the sequence length and the
share of distinct templates, into a gradient-boosted classifier.

Two classic baselines on exactly the same test blocks:

* **PCA** (Xu et al., SOSP 2009 — the paper that labelled this data): fit on
  training normals, flag blocks whose residual is beyond the threshold chosen
  on the validation slice.
* **Unseen template**: flag any block containing a template never seen in a
  training normal block. Simple, and a strong baseline on HDFS.

Weights are not saved: the data is research-use only (datasheets.md).

**Exported model (27 Oct 2026).** The trained booster is written to
`model.json` for `pashupatastra.trees`, with its threshold and event
vocabulary. LogHub is research-use only, so the model is released for research
use only (owner decision; docs/research/datasheets.md).
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from sati.sources import loghub

PARAMS: dict[str, object] = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 50,
    "feature_fraction": 0.9,
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
SPLIT = (0.6, 0.2, 0.2)


DATASETS = {
    "hdfs": {"model": "sati-kalaratri-v0", "name": "LogHub HDFS_v1", "unit": "HDFS blocks", "dtype": float},
    # float32: BGL's vocabulary is wider, and float64 would not fit a runner.
    "bgl": {"model": "sati-kalaratri-bgl-v0", "name": "LogHub BGL", "unit": "windows of 100 lines",
            "dtype": np.float32},
}


def featurise(events: pd.Series, vocab: list[str], dtype: type = float) -> pd.DataFrame:
    index = {e: i for i, e in enumerate(vocab)}
    matrix = np.zeros((len(events), len(vocab) + 3), dtype=dtype)
    for row, seq in enumerate(events):
        counts = Counter(seq)
        for event, n in counts.items():
            j = index.get(event)
            if j is None:
                matrix[row, len(vocab)] += n  # unseen in training
            else:
                matrix[row, j] = n
        matrix[row, len(vocab) + 1] = len(seq)
        matrix[row, len(vocab) + 2] = (len(counts) / len(seq)) if seq else 0.0
    return pd.DataFrame(matrix, columns=[*vocab, "unseen", "length", "distinct_share"])


def novelty(events: pd.Series, rare: int = 5) -> pd.DataFrame:
    """How new each window's lines are, judged only against the log before it.

    `featurise`'s "unseen" column counts templates missing from the training
    vocabulary, which is always zero on the training rows, so a model can never
    learn from it. These are causal instead: walking the log in order, a line
    is new if its template has not appeared earlier in the log at all, and rare
    if it has appeared fewer than `rare` times. Training, validation and test
    windows are measured the same way, and none sees its own future.
    """
    seen: Counter = Counter()
    rows = []
    for seq in events:
        rows.append((sum(seen[e] == 0 for e in seq), len({e for e in seq if seen[e] == 0}),
                     sum(seen[e] < rare for e in seq)))
        seen.update(seq)
    return pd.DataFrame(rows, columns=["first_seen_lines", "first_seen_templates", "rare_lines"], index=events.index)


def metrics(y: np.ndarray, flag: np.ndarray) -> dict[str, float]:
    tp = int(((flag == 1) & (y == 1)).sum())
    fp = int(((flag == 1) & (y == 0)).sum())
    fn = int(((flag == 0) & (y == 1)).sum())
    tn = int(((flag == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 5) if fp + tn else 0.0,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def best_threshold(y: np.ndarray, scores: np.ndarray) -> float:
    candidates = np.unique(np.quantile(scores, np.linspace(0.5, 0.999, 200)))
    return float(max(candidates, key=lambda t: metrics(y, (scores >= t).astype(int))["f1"]))


def pca_scores(train_normal: np.ndarray, X: np.ndarray, variance: float = 0.95) -> np.ndarray:
    """Squared prediction error after projecting off the principal subspace."""
    mean = train_normal.mean(axis=0)
    std = train_normal.std(axis=0)
    std[std == 0] = 1.0
    Z = (train_normal - mean) / std
    _, s, vt = np.linalg.svd(Z, full_matrices=False)
    explained = np.cumsum(s**2) / np.sum(s**2)
    k = int(np.searchsorted(explained, variance) + 1)
    P = vt[:k].T
    Xz = (X - mean) / std
    residual = Xz - Xz @ P @ P.T
    return (residual**2).sum(axis=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/loghub"))
    parser.add_argument("--out", type=Path, default=Path("results/kalaratri"))
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="hdfs")
    args = parser.parse_args()
    spec = DATASETS[args.dataset]

    started = time.time()
    data = loghub.blocks(args.cache) if args.dataset == "hdfs" else loghub.bgl_windows(args.cache)
    n = len(data)
    a, b = int(n * SPLIT[0]), int(n * (SPLIT[0] + SPLIT[1]))
    train, val, test = data.iloc[:a], data.iloc[a:b], data.iloc[b:]
    print(f"{spec['name']}: {n} {spec['unit']} ({data['anomaly'].mean():.2%} anomalous); "
          f"train {len(train)}, val {len(val)}, test {len(test)}")

    vocab = sorted({e for seq in train["events"] for e in seq})
    Xtr, Xva, Xte = (featurise(part["events"], vocab, spec["dtype"]) for part in (train, val, test))
    ytr, yva, yte = (part["anomaly"].to_numpy() for part in (train, val, test))

    booster = lgb.train({**PARAMS, "scale_pos_weight": float((ytr == 0).sum() / max(1, (ytr == 1).sum()))},
                        lgb.Dataset(Xtr, label=ytr), num_boost_round=ROUNDS)
    t_model = best_threshold(yva, booster.predict(Xva))
    kalaratri = metrics(yte, (booster.predict(Xte) >= t_model).astype(int))

    # v1: the same booster with the causal novelty features, over the log in order.
    fresh = novelty(data["events"]).astype(spec["dtype"])
    Ntr, Nva, Nte = (pd.concat([X, fresh.loc[part.index]], axis=1) for X, part in
                     ((Xtr.set_axis(train.index), train), (Xva.set_axis(val.index), val), (Xte.set_axis(test.index), test)))
    booster_v1 = lgb.train({**PARAMS, "scale_pos_weight": float((ytr == 0).sum() / max(1, (ytr == 1).sum()))},
                           lgb.Dataset(Ntr, label=ytr), num_boost_round=ROUNDS)
    t_v1 = best_threshold(yva, booster_v1.predict(Nva))
    with_novelty = metrics(yte, (booster_v1.predict(Nte) >= t_v1).astype(int))

    normal = Xtr[ytr == 0].to_numpy()
    t_pca = best_threshold(yva, pca_scores(normal, Xva.to_numpy()))
    pca = metrics(yte, (pca_scores(normal, Xte.to_numpy()) >= t_pca).astype(int))

    seen_normal = {e for seq, y in zip(train["events"], ytr, strict=True) if y == 0 for e in seq}
    unseen = metrics(yte, test["events"].map(lambda seq: int(any(e not in seen_normal for e in seq))).to_numpy())

    importance = sorted(zip(Xtr.columns, booster.feature_importance("gain"), strict=True), key=lambda x: -x[1])[:8]
    results = {
        "model": spec["model"],
        "dataset": {"name": spec["name"], "zenodo_record": loghub.RECORD, "blocks": n,
                    **({} if args.dataset == "hdfs" else {"unit": spec["unit"]}),
                    "anomaly_share": round(float(data["anomaly"].mean()), 4),
                    "split": {"train": len(train), "validation": len(val), "test": len(test), "order": "as logged"}},
        "vocabulary": len(vocab),
        "test": {spec["model"].removeprefix("sati-"): kalaratri,
                 spec["model"].removeprefix("sati-").replace("-v0", "-v1") + " (+ novelty)": with_novelty,
                 "pca (Xu et al. 2009)": pca, "unseen-template rule": unseen},
        "thresholds": {spec["model"].removeprefix("sati-"): t_model, "v1": t_v1, "pca": t_pca},
        "top_features": [
            {"feature": f, "gain": round(float(g), 1),
             **({"template": data.attrs["templates"][f]} if f in data.attrs.get("templates", {}) else {})}
            for f, g in importance
        ],
        "weights_published": True,
        "weights_note": "Research use only, not for commercial use (CC BY-NC-SA 4.0): trained on research-use-only data; owner decision, 27 Oct 2026. LogHub is research-use only.",
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    from pashupatastra import trees

    (args.out / "model.json").write_text(json.dumps({
        **trees.compact(booster.dump_model(), list(Xtr.columns)), "threshold": float(t_model),
        "vocabulary": vocab, "dataset": spec["name"],
        # Held-out sessions from the later part of the log, for the live demo.
        "examples": [{"id": f"session-{i}", "label": "failing" if yte[i] else "normal", "truth": int(yte[i]),
                      "features": {c: float(Xte.iloc[i][c]) for c in Xtr.columns}}
                     for i in [*np.flatnonzero(yte == 1)[:12], *np.flatnonzero(yte == 0)[:12]]], "licence": "Research use only, not for commercial use (CC BY-NC-SA 4.0): trained on research-use-only data; owner decision, 27 Oct 2026."}), encoding="utf-8")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for name, m in results["test"].items():
        print(f"  {name:24} P {m['precision']:.3f} R {m['recall']:.3f} F1 {m['f1']:.3f} FPR {m['false_positive_rate']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
