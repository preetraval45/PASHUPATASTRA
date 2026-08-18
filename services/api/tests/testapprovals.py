"""The approval endpoints.

Covers the three things the HTTP layer adds over the core module: a stale verdict
must fail loudly, a denial must not be an error, and the fatigue numbers must be
reachable by someone who did not write the code.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from pashupatastra.dharma import Tier, Verdict

from app.api.routes import APPROVALS
from app.main import app

client = TestClient(app)
NOW = datetime.now().astimezone()


def a_verdict(expires_in_minutes: int = 15, tier: Tier = Tier.APPROVAL) -> dict:
    return Verdict(
        action_id="rollback_deployment",
        incident_ref="INC-1",
        base_risk=45,
        adjustments=[],
        effective_risk=45,
        tier=tier,
        required_approvers=["sre-oncall"],
        expires_at=NOW + timedelta(minutes=expires_in_minutes),
    ).model_dump(mode="json")


def setup_function() -> None:
    """A fresh log per test — fatigue is cumulative and would leak between them."""
    APPROVALS._requests.clear()


# --- approve ------------------------------------------------------------------


def test_approving_records_the_approver() -> None:
    response = client.post(
        "/api/v1/policy/approve", json={"verdict": a_verdict(), "approver": "alice"}
    )
    assert response.status_code == 200
    assert response.json()["granted_by"] == "human:alice"


def test_a_denied_verdict_cannot_be_approved() -> None:
    response = client.post(
        "/api/v1/policy/approve",
        json={"verdict": a_verdict(tier=Tier.DENIED), "approver": "alice"},
    )
    assert response.status_code == 403


def test_an_expired_verdict_fails_loudly_rather_than_quietly_succeeding() -> None:
    """Otherwise the operator believes they authorised something, and only
    `is_executable` disagrees — later, somewhere else."""
    response = client.post(
        "/api/v1/policy/approve",
        json={"verdict": a_verdict(expires_in_minutes=-1), "approver": "alice"},
    )
    assert response.status_code == 409
    assert "expired" in response.json()["detail"]


# --- deny ---------------------------------------------------------------------


def test_denial_is_not_an_error() -> None:
    """Expressing it as an HTTP error would make the client's success path the
    one where a human said yes."""
    response = client.post(
        "/api/v1/policy/deny",
        json={
            "verdict": a_verdict(),
            "approver": "alice",
            "reason": "blast radius too wide during business hours",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["denial_reason"].startswith("blast radius")
    assert body["granted_by"] is None, "a denied verdict grants nothing"


# --- fatigue ------------------------------------------------------------------


def test_fatigue_is_reachable_without_reading_the_source() -> None:
    """A metric nobody looks at cannot change behaviour."""
    client.post("/api/v1/policy/approve", json={"verdict": a_verdict(), "approver": "alice"})
    body = client.get("/api/v1/policy/approvals/fatigue").json()

    assert "looks_decorative" in body
    assert body["decisions"] == 1
    assert "alice" in body["by_approver"]


def test_rubber_stamping_shows_up_in_the_measurement() -> None:
    """Twelve instant approvals is the pattern the metric exists to catch."""
    for _ in range(12):
        client.post(
            "/api/v1/policy/approve",
            json={"verdict": a_verdict(), "approver": "rusher"},
        )
    body = client.get("/api/v1/policy/approvals/fatigue").json()

    assert body["approval_rate"] == 1.0
    assert body["fast_decision_rate"] == 1.0
    assert body["looks_decorative"] is True


def test_deliberated_approvals_do_not_look_decorative() -> None:
    """The same approval rate, with time taken, is a system working."""
    presented = (NOW - timedelta(minutes=2)).isoformat()
    for _ in range(12):
        client.post(
            "/api/v1/policy/approve",
            json={"verdict": a_verdict(), "approver": "careful", "presented_at": presented},
        )
    body = client.get("/api/v1/policy/approvals/fatigue").json()

    assert body["approval_rate"] == 1.0
    assert body["looks_decorative"] is False


def test_the_summary_leads_with_the_uncomfortable_number() -> None:
    client.post("/api/v1/policy/approve", json={"verdict": a_verdict(), "approver": "alice"})
    assert list(client.get("/api/v1/policy/approvals/fatigue").json())[0] == "looks_decorative"
