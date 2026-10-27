"""The plain-Python tree evaluator (pashupatastra.trees) matches LightGBM exactly.

The API serves Sati's boosters through it, so a mismatch would mean visitors
see a different model from the one evaluated.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pytest
from pashupatastra import trees


@pytest.mark.parametrize("objective", ["binary", "lambdarank"])
@pytest.mark.parametrize("zero_as_missing", [False, True])
def test_plain_python_matches_lightgbm_with_missing_values(objective, zero_as_missing):
    rng = np.random.default_rng(3)
    x = rng.normal(size=(600, 5))
    x[rng.random(x.shape) < 0.15] = np.nan  # missing values on every feature
    x[rng.random(x.shape) < 0.10] = 0.0
    y = ((np.nan_to_num(x[:, 0]) + np.nan_to_num(x[:, 2]) > 0)).astype(int)
    params = {"objective": objective, "verbose": -1, "num_leaves": 8, "min_data_in_leaf": 5,
              "zero_as_missing": zero_as_missing}
    data = lgb.Dataset(x, label=y, group=[30] * 20 if objective == "lambdarank" else None)
    booster = lgb.train(params, data, num_boost_round=25)
    model = trees.compact(booster.dump_model(), [f"f{i}" for i in range(5)])
    expected = booster.predict(x, raw_score=objective == "lambdarank")
    got = np.array([trees.predict(model, [None if np.isnan(v) else float(v) for v in row]) for row in x])
    assert np.allclose(got, expected, atol=1e-9)


def test_features_are_read_by_name_and_absent_ones_are_missing():
    model = {"objective": "binary", "features": ["a", "b"], "trees": [[1, 0.5, True, 1, -1.0, 1.0]]}
    assert trees.row_from(model, {"a": 3.0}) == [3.0, None]
    assert trees.raw_score(model, trees.row_from(model, {"a": 3.0})) == -1.0  # missing b goes left
