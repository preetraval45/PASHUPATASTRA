"""Kalaratri v0 — features, metrics and the PCA baseline, on synthetic blocks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from sati.logs.run import best_threshold, featurise, metrics, pca_scores


def test_templates_outside_the_training_vocabulary_are_counted_as_unseen():
    frame = featurise(pd.Series([["E1", "E2", "E9"]]), vocab=["E1", "E2"])
    row = frame.iloc[0]
    assert (row["E1"], row["E2"], row["unseen"], row["length"]) == (1, 1, 1, 3)


def test_metrics_count_every_cell():
    m = metrics(np.array([1, 1, 0, 0]), np.array([1, 0, 1, 0]))
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (1, 1, 1, 1)
    assert m["precision"] == m["recall"] == m["f1"] == 0.5


def test_pca_scores_unusual_blocks_higher():
    rng = np.random.default_rng(0)
    normal = rng.normal(0, 1, (500, 3)) @ np.array([[1, 1, 0], [0, 1, 1], [0, 0, 0.01]])
    usual = normal[:5]
    odd = np.array([[0.0, 0.0, 8.0]])
    scores = pca_scores(normal, np.vstack([usual, odd]), variance=0.9)
    assert scores[-1] > scores[:-1].max()


def test_the_threshold_is_chosen_from_scores_not_labels_alone():
    y = np.array([0] * 90 + [1] * 10)
    scores = np.concatenate([np.linspace(0, 0.4, 90), np.linspace(0.8, 1.0, 10)])
    t = best_threshold(y, scores)
    assert metrics(y, (scores >= t).astype(int))["f1"] == 1.0
