"""Mahagauri v0 — episodes, the all-clear rule, outcomes and the whole run, on synthetic servers."""

from __future__ import annotations

import json
import sys

import numpy as np

from sati.sources import smd
from sati.verify import report
from sati.verify import run as verify


def test_all_clear_needs_consecutive_recovered_minutes():
    assert verify.all_clear(np.array([1, 1, 0, 1, 1, 1, 0])) == 5
    assert verify.all_clear(np.array([1, 0, 1, 0])) is None


def test_outcomes_separate_premature_confirmed_and_unconfirmed():
    ep = {"start": 100, "end": 110, "stop": 140}
    early = np.zeros(40, dtype=bool)
    early[2:5] = True
    late = np.zeros(40, dtype=bool)
    late[13:16] = True
    assert verify.outcome(ep, early) == {"result": "premature", "early_by": 6}
    assert verify.outcome(ep, late) == {"result": "confirmed", "delay": 5}
    assert verify.outcome(ep, np.zeros(40, dtype=bool)) == {"result": "unconfirmed"}


def test_labels_turn_on_exactly_when_the_anomaly_ends():
    y = verify.labels({"start": 10, "end": 15, "stop": 20})
    assert y.tolist() == [0] * 5 + [1] * 5


def test_baseline_distance_is_measured_against_the_pre_incident_hour():
    rng = np.random.default_rng(0)
    pre = rng.normal(10, 1, size=(60, 2))
    window = np.array([[10.0, 10.0], [30.0, 10.0]])
    d = verify.baseline_distance(pre, window)
    assert d[0].max() < 1 and d[1, 0] > 10 and d[1, 1] < 1


def _machine(name: str, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    train, test = rng.normal(size=(400, 38)), rng.normal(size=(900, 38))
    labels = np.zeros(900, dtype=int)
    for start in (150, 450, 700):
        test[start : start + 40, :6] += 9  # the fault, then a clean return to normal
        labels[start : start + 40] = 1
    return {"name": name, "group": smd.group(name), "train": train, "test": test, "labels": labels}


def test_the_whole_run_and_report(tmp_path, monkeypatch, capsys):
    names = ("machine-1-1", "machine-1-2", "machine-2-1", "machine-2-2")
    monkeypatch.setattr(smd, "MACHINES", names)
    monkeypatch.setattr(smd, "machine", lambda name, cache, rev: _machine(name, names.index(name)))
    monkeypatch.setattr(sys, "argv", ["verify", "--out", str(tmp_path), "--cache", str(tmp_path)])
    assert verify.main() == 0
    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert set(results["pooled"]) == {"mahagauri-v0", "mahagauri-v1 (upper-bound threshold)",
                                      "mahagauri-v1 + 3σ agreement", "mahagauri-v2 (out-of-fold, hold chosen)",
                                      "mahagauri-v2 + 3σ agreement", "back within 3σ", "fixed timer"}
    assert results["dataset"]["incidents"] == 12
    assert results["pooled"]["mahagauri-v0"]["confirmed_rate"] > 0.5  # clean recoveries are confirmable
    assert report.main(str(tmp_path / "results.json")) == 0
    assert "Premature all-clear" in capsys.readouterr().out


def test_the_upper_bound_is_stricter_than_the_point_estimate():
    assert verify.wilson_upper(5, 100) > 0.05
    assert verify.wilson_upper(0, 200) < 0.02


def test_a_longer_hold_declares_later_or_never():
    recovered = np.array([0, 1, 1, 1, 0, 1, 1, 1, 1, 1], dtype=bool)
    assert verify.all_clear(recovered, 3) == 3
    assert verify.all_clear(recovered, 5) == 9
    assert verify.all_clear(recovered, 10) is None


def test_v2_picks_the_setting_that_confirms_most_within_budget():
    # 80 incidents ending at minute 10 (with 40, zero early calls still has a
    # 95% upper bound above 5%, so nothing would be within budget); the score turns "recovered" at minute 8
    # (two minutes early) and stays there. A hold of 3 declares at minute 10,
    # which is on time; nothing here declares early, so the lowest threshold
    # and shortest hold win, and the choice is deterministic.
    eps = [{"start": 0, "end": 10, "stop": 30, "group": "g"} for _ in range(80)]
    probs = [np.r_[np.zeros(8), np.ones(22)] for _ in eps]
    t, hold = verify.choose_v2(eps, probs)
    assert hold == 3 and t == verify.THRESHOLDS[0]
