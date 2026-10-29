"""Kalaratri and Chandraghanta, served: score a held-out example live, truth and licence beside it."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.engines import treedemo
from app.main import app

client = TestClient(app)

MODEL = {
    "objective": "binary", "features": ["E5"], "trees": [[0, 2.0, True, 0, -3.0, 3.0]], "threshold": 0.5,
    "dataset": "LogHub HDFS_v1", "licence": "Research use only",
    "examples": [{"id": "session-1", "label": "failing", "truth": 1, "features": {"E5": 4.0}},
                 {"id": "session-2", "label": "normal", "truth": 0, "features": {"E5": 0.0}}],
}


@pytest.fixture
def served(tmp_path, monkeypatch):
    (tmp_path / "kalaratri.json").write_text(json.dumps(MODEL), encoding="utf-8")
    monkeypatch.setattr(treedemo, "FOLDER", tmp_path)
    treedemo.served.cache_clear()
    yield
    treedemo.served.cache_clear()


def test_scores_a_held_out_example_with_its_truth_and_licence(served):
    body = client.get("/api/v1/models/kalaratri/examples/session-1").json()
    assert body["flagged"] is True and body["truth"] is True and body["correct"] is True
    assert body["licence"] == "Research use only"
    assert client.get("/api/v1/models/kalaratri/examples/session-2").json()["flagged"] is False
    why = client.get("/api/v1/models/kalaratri/examples/session-1").json()["why"]
    assert why == [{"feature": "E5", "value": 4.0, "effect": 6.0}]  # the one split, -3 -> +3


def test_lists_examples_and_refuses_other_forms_and_unknown_ids(served):
    assert [e["id"] for e in client.get("/api/v1/models/kalaratri/examples").json()["examples"]] == ["session-1", "session-2"]
    assert client.get("/api/v1/models/katyayani/examples").status_code == 404
    assert client.get("/api/v1/models/kalaratri/examples/nope").status_code == 404
    assert client.get("/api/v1/models/chandraghanta/examples").status_code == 503  # not exported in this fixture
