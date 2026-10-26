"""Shailaputri v0 — a learned anomaly detector over causal features.

A gradient-boosted classifier scores each point as "inside an anomaly window or
not" from features of its own past (`features.py`). The decision threshold is
chosen on training series only. Scored by `pashupatastra.evaluation.evaluate`,
the same online harness that scores the four statistical strategies, so the
comparison is like for like.

Parameters fixed here, before any result (RESEARCH PLAN.md rule 3).
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from pashupatastra.baselines import Band, Reading

from sati.detect.features import WARMUP

PARAMS: dict[str, object] = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 200,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "is_unbalance": True,
    "verbosity": -1,
    "seed": 7,
    "deterministic": True,
    "force_row_wise": True,
    # `deterministic` holds only for a fixed thread count; runners vary, and on
    # 26 Oct the same code and data gave four different Shailaputri models.
    "num_threads": 2,
}
ROUNDS = 300
THRESHOLDS = tuple(round(t, 2) for t in np.arange(0.3, 0.96, 0.05))


def train(frames: list[pd.DataFrame], labels: list[np.ndarray]) -> lgb.Booster:
    X = pd.concat([f.iloc[WARMUP:] for f in frames], ignore_index=True)
    y = np.concatenate([lab[WARMUP:] for lab in labels])
    return lgb.train(PARAMS, lgb.Dataset(X, label=y), num_boost_round=ROUNDS)


def probabilities(booster: lgb.Booster, frame: pd.DataFrame) -> np.ndarray:
    p = booster.predict(frame)
    p[:WARMUP] = np.nan
    return p


class Replay:
    """A `DetectionStrategy` that replays precomputed decisions in order.

    The features are causal, so deciding the whole series at once is the same
    decision an online detector would make point by point. `evaluate` still
    drives it one value at a time and owns all the scoring.
    """

    name = "shailaputri-v0"

    def __init__(self, probs: np.ndarray, threshold: float) -> None:
        self.probs, self.threshold, self.i = probs, threshold, 0

    def evaluate_and_observe(self, value: float) -> Reading:
        p = self.probs[self.i]
        self.i += 1
        if np.isnan(p):
            band = Band.UNKNOWN
        else:
            band = Band.HIGH if p >= self.threshold else Band.NORMAL
        return Reading(band=band, value=float(value), median=None, deviation=0.0 if np.isnan(p) else float(p), samples=self.i)
