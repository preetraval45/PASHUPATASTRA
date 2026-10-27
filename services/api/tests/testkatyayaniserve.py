"""Katyayani, served: ranks a reserved incident live and shows the truth beside it."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.engines import katyayani
from app.main import app

client = TestClient(app)

# One split: services with a peak above 5 score high. "db" is the root.
MODEL = {
    "model": "katyayani",
    "features": ["peak"],
    "booster": {"objective": "lambdarank", "features": ["peak"], "trees": [[0, 5.0, True, 1, -1.0, 2.0]]},
    "trained_on": {"incidents": 10, "systems": ["Sock Shop"]},
    "reserved": {"incidents": 1, "rca@1": 1.0},
    "cases": [{"id": "case-1", "system": "Sock Shop", "root": "db", "services": [
        {"name": "web", "features": {"peak": 1.0}, "shown": {"peak": 1.0}},
        {"name": "db", "features": {"peak": 9.0}, "shown": {"peak": 9.0}},
    ]}],
}


@pytest.fixture
def served(tmp_path, monkeypatch):
    path = tmp_path / "katyayani.json"
    path.write_text(json.dumps(MODEL), encoding="utf-8")
    monkeypatch.setattr(katyayani, "MODEL", path)
    katyayani.served.cache_clear()
    yield
    katyayani.served.cache_clear()


def test_lists_only_reserved_incidents(served):
    body = client.get("/api/v1/models/katyayani/cases").json()
    assert body["cases"] == [{"id": "case-1", "system": "Sock Shop", "services": 2}]


def test_ranks_live_and_shows_the_truth(served):
    body = client.get("/api/v1/models/katyayani/cases/case-1").json()
    assert [r["service"] for r in body["ranking"]] == ["db", "web"]
    assert body["root"] == "db" and body["correct"] is True and body["position"] == 1


def test_unknown_case_is_404_and_a_missing_model_is_503(served, monkeypatch, tmp_path):
    assert client.get("/api/v1/models/katyayani/cases/nope").status_code == 404
    monkeypatch.setattr(katyayani, "MODEL", tmp_path / "absent.json")
    assert client.get("/api/v1/models/katyayani/cases").status_code == 503
