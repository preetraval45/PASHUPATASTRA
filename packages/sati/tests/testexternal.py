"""RP-32: the RCAEval adapter keeps the answer out of the inputs, and the subset is locked."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sati.rca import external

SUBSET = Path(__file__).resolve().parents[3] / "benchmark" / "external" / "rcaeval" / "subset.json"


def test_the_committed_subset_matches_its_hash_and_its_rule():
    subset = external.load_subset(SUBSET)
    assert subset["counts"] == {"ob": 245, "ss": 245}
    assert all(c.startswith(("re1ob", "re1ss", "re2ob", "re2ss", "re3ob", "re3ss")) for c in subset["cases"])


def test_an_edited_subset_is_refused(tmp_path):
    subset = json.loads(SUBSET.read_text(encoding="utf-8"))
    subset["cases"] = subset["cases"][1:]
    path = tmp_path / "subset.json"
    path.write_text(json.dumps(subset), encoding="utf-8")
    with pytest.raises(ValueError, match="no longer matches"):
        external.load_subset(path)


def test_inputs_carry_no_label_and_name_no_answer(monkeypatch, tmp_path):
    times = np.arange(0, 1800, 15)
    frame = pd.DataFrame({"time": times,
                          "paymentservice_cpu": np.where(times >= 900, 9.0, 1.0) + np.random.default_rng(0).normal(0, 0.1, len(times)),
                          "checkoutservice_latency": np.where(times >= 960, 5.0, 1.0),
                          "frontend_latency": 1.0})
    monkeypatch.setattr(external.rcaeval, "metrics", lambda case, cache, rev: frame)
    case = pd.Series({"case": "re2ob_paymentservice_cpu_1", "system": "ob", "inject_time": 900,
                      "root_cause_service": "paymentservice", "fault": "cpu", "fault_description": "cpu hog"})
    out = external.inputs(case, tmp_path, "rev")
    assert "label" not in out.columns
    assert not set(external.LABEL_FIELDS) & set(out.columns)
    assert external.answer(case) == "paymentservice"
    assert set(out["service"]) >= {"paymentservice", "checkoutservice", "frontend"}  # every candidate, not the answer
