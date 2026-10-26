"""Shailaputri v1 on SMD — ranges, onset weights, causal aggregation and the whole run, on synthetic machines."""

from __future__ import annotations

import json
import sys

import numpy as np

from sati.detect import smd as run
from sati.sources import smd


def test_ranges_are_runs_of_ones():
    assert smd.ranges(np.array([0, 1, 1, 0, 0, 1, 0, 1])) == [(1, 3), (5, 6), (7, 8)]
    assert smd.ranges(np.zeros(5, dtype=int)) == []


def test_machine_groups_follow_the_names():
    assert smd.group("machine-3-11") == "machine-3"
    assert len(smd.MACHINES) == 28 and len({smd.group(m) for m in smd.MACHINES}) == 3


def test_onset_weights_lift_the_start_of_each_anomaly_only():
    labels = np.zeros(100, dtype=int)
    labels[10:60] = 1
    w = run.onset_weights(labels)
    assert (w[10:20] == run.ONSET_WEIGHT).all() and (w[20:60] == 1).all() and (w[:10] == 1).all()


def test_aggregated_features_never_look_ahead():
    rng = np.random.default_rng(0)
    train, test = rng.normal(size=(400, 3)), rng.normal(size=(200, 3))
    changed = test.copy()
    changed[150:] += 50
    a, b = run.aggregate(train, test), run.aggregate(train, changed)
    assert np.allclose(a.iloc[:150].to_numpy(), b.iloc[:150].to_numpy(), equal_nan=True)
    assert (b["max_z_12"].iloc[150] > a["max_z_12"].iloc[150])


def _machine(name: str, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    train, test = rng.normal(size=(400, 38)), rng.normal(size=(600, 38))
    labels = np.zeros(600, dtype=int)
    for start in (150, 400):
        test[start : start + 30, :5] += 8
        labels[start : start + 30] = 1
    return {"name": name, "group": smd.group(name), "train": train, "test": test, "labels": labels}


def test_the_whole_run_holds_out_groups_and_writes_results(tmp_path, monkeypatch):
    names = ("machine-1-1", "machine-1-2", "machine-2-1", "machine-2-2")
    monkeypatch.setattr(smd, "MACHINES", names)
    monkeypatch.setattr(smd, "machine", lambda name, cache, rev: _machine(name, names.index(name)))
    monkeypatch.setattr(sys, "argv", ["smd", "--out", str(tmp_path), "--cache", str(tmp_path)])
    assert run.main() == 0
    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert [f["held_out"] for f in results["folds"]] == ["machine-1", "machine-2"]
    assert set(results["mean_across_groups"]) == {"shailaputri-v1", "shailaputri-v1 onset-weighted",
                                                  "max robust z", "pca per machine"}
    assert results["mean_across_groups"]["shailaputri-v1"]["recall"] > 0.5  # planted shifts are findable
    from sati.detect import smdreport

    assert smdreport.main(str(tmp_path / "results.json")) == 0
