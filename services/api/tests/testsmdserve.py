"""The server models, served: run live on a held-out incident, truth beside the answer."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.engines import smdserve
from app.main import app

client = TestClient(app)

# Feature 0 is a "deviation"; anomalous minutes have it high. Six minutes, the
# incident is minutes 2–3 (end exclusive at 4).
DEV = [0.1, 0.2, 5.0, 6.0, 0.1, 0.1]
STUMP = {"objective": "binary", "features": ["dev"], "trees": [[0, 1.0, True, 1, -3.0, 3.0]]}
MAHA = {"objective": "binary", "features": ["dev", "pre_beyond_3"], "trees": [[0, 1.0, True, 1, 3.0, -3.0]],
        "threshold": 0.5, "hold": 2}
MODEL = {
    "held_out_group": "machine-3", "trained_on": ["machine-1", "machine-2"],
    "models": {
        "shailaputri": {**STUMP, "threshold": 0.5},
        "siddhidatri_input": STUMP,
        "siddhidatri": {"weights": [4.0, 0.0, 0.0, -2.0], "threshold": 0.5},
        "mahagauri": MAHA,
    },
    "incidents": [{
        "id": "machine-3-1@100", "machine": "machine-3-1", "minutes": 6, "incident": [2, 4],
        "truth": [0, 0, 1, 1, 0, 0],
        "features": [[v] for v in DEV],
        "statistical": [[0.0, 0.0]] * 6,
        # From onset: anomalous twice, then calm with nothing beyond 3σ.
        "verify": [[5.0, 2.0], [6.0, 1.0], [0.1, 0.0], [0.1, 0.0]],
    }],
}


@pytest.fixture
def served(tmp_path, monkeypatch):
    path = tmp_path / "smd.json"
    path.write_text(json.dumps(MODEL), encoding="utf-8")
    monkeypatch.setattr(smdserve, "MODEL", path)
    smdserve.served.cache_clear()
    yield
    smdserve.served.cache_clear()


def test_all_three_run_live_beside_the_truth(served):
    body = client.get("/api/v1/models/servers/incidents/machine-3-1@100").json()
    assert body["shailaputri"]["flags"] == [False, False, True, True, False, False]
    assert body["shailaputri"]["caught"] and body["shailaputri"]["first_flag"] == 2
    assert body["shailaputri"]["false_flags_before"] == 0
    assert body["siddhidatri"]["flags"][2] and not body["siddhidatri"]["flags"][0]
    # Recovered at verify minutes 2 and 3 (hold 2) → declared at onset + 3 = minute 5, after the end (4).
    assert body["mahagauri"] == {"declared_over": 5, "verdict": "confirmed"}


def test_lists_incidents_and_refuses_unknown_ones(served):
    listed = client.get("/api/v1/models/servers/incidents").json()
    assert listed["incidents"] == [{"id": "machine-3-1@100", "machine": "machine-3-1", "minutes": 6, "length": 2}]
    assert client.get("/api/v1/models/servers/incidents/nope").status_code == 404
