"""Sati-RCA v0: a gradient-boosted ranker over per-service features.

LightGBM `lambdarank`, one query per incident, one candidate per service, label
1 for the true root cause. A ranker rather than a classifier because the task is
"which of these services first", and the number of services differs between
systems — a classifier over service *names* could not transfer to a system it
has never seen; a ranker over service *features* can.

The parameters are fixed here, in the commit that precedes the first result
(RESEARCH PLAN.md rule 3, pre-declare). Nothing is tuned on a test split.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

#: Pre-declared. Small trees and strong regularisation: a few hundred
#: incidents is little data, and the job is to generalise across systems.
RANKER_PARAMS: dict[str, object] = {
    "objective": "lambdarank",
    "metric": "ndcg",
    "ndcg_eval_at": [1, 3, 5],
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
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
RANKER_ROUNDS = 300

FAULT_PARAMS: dict[str, object] = {
    "objective": "multiclass",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 10,
    "feature_fraction": 0.8,
    "lambda_l2": 1.0,
    "verbosity": -1,
    "seed": 7,
    "deterministic": True,
    "force_row_wise": True,
    # `deterministic` holds only for a fixed thread count; runners vary, and on
    # 26 Oct the same code and data gave four different Shailaputri models.
    "num_threads": 2,
}
FAULT_ROUNDS = 200


def train_ranker(table: pd.DataFrame, features: list[str]) -> lgb.Booster:
    ordered = table.sort_values(["case", "service"], kind="stable")
    groups = ordered.groupby("case", sort=False).size().to_numpy()
    data = lgb.Dataset(ordered[features], label=ordered["label"], group=groups, free_raw_data=False)
    return lgb.train(RANKER_PARAMS, data, num_boost_round=RANKER_ROUNDS)


def rank(table: pd.DataFrame, scores: np.ndarray) -> dict[str, list[str]]:
    """Services per incident, best first. Ties broken by name so a run is
    reproducible rather than dependent on row order."""
    scored = table.assign(score=scores)
    ordered = scored.sort_values(["case", "score", "service"], ascending=[True, False, True])
    return {case: list(group["service"]) for case, group in ordered.groupby("case", sort=False)}


def predict(booster: lgb.Booster, table: pd.DataFrame, features: list[str]) -> dict[str, list[str]]:
    return rank(table, booster.predict(table[features]))


def baseline(table: pd.DataFrame) -> dict[str, list[str]]:
    """No learning: rank by the largest robust shift any of a service's series
    showed. The statistical ranker Sati-RCA has to beat to justify being a model."""
    return rank(table, table["peak_any"].fillna(-np.inf).to_numpy())


def position(ranking: list[str], root: str) -> int | None:
    return ranking.index(root) + 1 if root in ranking else None


def train_fault(rows: pd.DataFrame, features: list[str], classes: list[str]) -> lgb.Booster:
    params = {**FAULT_PARAMS, "num_class": len(classes)}
    labels = rows["fault"].map({c: i for i, c in enumerate(classes)})
    return lgb.train(params, lgb.Dataset(rows[features], label=labels), num_boost_round=FAULT_ROUNDS)


def explain(
    booster: lgb.Booster,
    row: pd.DataFrame,
    features: list[str],
    provenance: dict[tuple[str, str], str],
    top: int = 3,
) -> list[dict[str, object]]:
    """The features that pushed one service up the ranking, each mapped to the
    metric series it was computed from — the citations a hypothesis carries."""
    contributions = booster.predict(row[features], pred_contrib=True)[0][:-1]
    service = str(row["service"].iloc[0])
    order = np.argsort(-contributions)
    reasons = []
    for index in order[:top]:
        if contributions[index] <= 0:
            break
        name = features[index]
        reasons.append(
            {
                "feature": name,
                "contribution": round(float(contributions[index]), 4),
                "value": None if pd.isna(row[name].iloc[0]) else round(float(row[name].iloc[0]), 4),
                "series": provenance.get((service, name.removeprefix("rank_"))),
            }
        )
    return reasons
