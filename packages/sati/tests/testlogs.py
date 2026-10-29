"""Kalaratri v0 — features, metrics and the PCA baseline, on synthetic blocks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from sati.loganomaly.run import best_threshold, featurise, metrics, novelty, pca_scores


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


def test_bgl_templates_mask_every_token_with_a_digit_and_read_the_label():
    from sati.sources.loghub import bgl_line

    head = "2005.06.11 R30-M0-N9-C:J16-U01 2005-06-11-17.32.07.581048 R30-M0-N9-C:J16-U01 RAS KERNEL"
    assert bgl_line(f"KERNDTLB 1118536327 {head} FATAL data TLB error interrupt at 0x0b85eee0 core 2") == (
        1, "data TLB error interrupt at <*> core <*>")
    assert bgl_line(f"- 1118536327 {head} INFO instruction cache parity error corrected") == (
        0, "instruction cache parity error corrected")
    assert bgl_line("too short") is None


def test_bgl_windows_are_consecutive_and_anomalous_if_any_line_is(tmp_path, monkeypatch):
    import zipfile

    from sati.sources import loghub

    head = "1 2005.06.03 N 2005-06-03-15.42.50.363779 N RAS KERNEL INFO"
    lines = [f"- {head} normal event {i}" for i in range(250)]
    lines[150] = f"KERNDTLB {head} bad event 7"
    with zipfile.ZipFile(tmp_path / "BGL.zip", "w") as zf:
        zf.writestr("BGL.log", "\n".join(lines) + "\n")
    monkeypatch.setattr(loghub, "archive", lambda cache, *a, **k: tmp_path / "BGL.zip")
    windows = loghub.bgl_windows(tmp_path, size=100)
    assert list(windows["anomaly"]) == [0, 1]  # the last 50 lines do not fill a window
    assert len(set(windows["events"][0])) == 1  # "normal event <*>" is one template


def test_novelty_is_judged_only_against_the_log_before_each_window():
    frame = novelty(pd.Series([["E1", "E1", "E2"], ["E1", "E3"], ["E3", "E3", "E4"]]), rare=2)
    # window 1: all new; window 2: E3 is new; window 3: E4 is new, E3 seen once (still rare at 2)
    assert frame["first_seen_lines"].tolist() == [3, 1, 1]
    assert frame["first_seen_templates"].tolist() == [2, 1, 1]
    assert frame["rare_lines"].tolist() == [3, 1, 3]
