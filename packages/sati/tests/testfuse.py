"""Siddhidatri v0 — the logistic fit, calibration measures and the whole run, on synthetic servers."""

from __future__ import annotations

import json
import sys

import numpy as np

from sati.fuse import report
from sati.fuse import run as fuse
from sati.sources import smd


def test_logistic_recovers_a_known_relationship():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(4000, 1))
    y = (rng.random(4000) < 1 / (1 + np.exp(-(2 * x[:, 0] - 1)))).astype(float)
    w = fuse.logistic(x, y)
    assert abs(w[0] - 2) < 0.25 and abs(w[1] + 1) < 0.25


def test_ece_is_zero_when_stated_rates_come_true_and_large_when_they_do_not():
    y = np.array([1, 0] * 50, dtype=float)
    assert fuse.ece(np.full(100, 0.5), y) == 0.0
    assert fuse.ece(np.full(100, 0.95), y) > 0.4


def test_brier_scores_confident_mistakes_worst():
    y = np.array([1.0, 0.0])
    assert fuse.brier(np.array([1.0, 0.0]), y) == 0.0
    assert fuse.brier(np.array([0.0, 1.0]), y) == 1.0


def _machine(name: str, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    train, test = rng.normal(size=(400, 38)), rng.normal(size=(700, 38))
    labels = np.zeros(700, dtype=int)
    for start in (150, 450):
        test[start : start + 30, :5] += 8
        labels[start : start + 30] = 1
    return {"name": name, "group": smd.group(name), "train": train, "test": test, "labels": labels}


def test_the_whole_run_fuses_out_of_fold_and_reports(tmp_path, monkeypatch, capsys):
    names = ("machine-1-1", "machine-1-2", "machine-2-1", "machine-2-2", "machine-3-1", "machine-3-2")
    monkeypatch.setattr(smd, "MACHINES", names)
    monkeypatch.setattr(smd, "machine", lambda name, cache, rev: _machine(name, names.index(name)))
    monkeypatch.setattr(sys, "argv", ["fuse", "--out", str(tmp_path), "--cache", str(tmp_path)])
    assert fuse.main() == 0
    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert [f["held_out"] for f in results["folds"]] == ["machine-1", "machine-2", "machine-3"]
    assert set(results["mean_across_groups"]) == {"siddhidatri-v0", *fuse.FEATURES}
    assert 0 <= results["mean_across_groups"]["siddhidatri-v0"]["ece"] <= 1
    assert report.main(str(tmp_path / "results.json")) == 0
    assert "calibrated verdict" in capsys.readouterr().out
