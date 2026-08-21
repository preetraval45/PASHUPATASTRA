"""API tests, centred on the Phase 3 exit criterion: no execution path reaches a
connector without a recorded policy verdict."""

from __future__ import annotations

import pytest
from app.main import app
from fastapi.testclient import TestClient
from pashupatastra import PolicyViolation

client = TestClient(app)


def evaluate(action_id: str, **kwargs: object) -> dict:
    body: dict[str, object] = {"action_id": action_id}
    body.update(kwargs)
    response = client.post("/api/v1/policy/evaluate", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_health_reports_dry_run_default() -> None:
    body = client.get("/api/v1/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert body["dry_run"] is True, "dry-run must be the default (SECURITY.md control 1)"


def test_health_flags_a_non_durable_audit_trail() -> None:
    """An in-memory audit trail must never report itself as healthy.

    Named against `memory` rather than a specific backend. Asserting
    `== "postgres"` encoded the bug it was meant to catch: it passed while a
    DynamoDB deployment reported the wrong store, and failed once the store
    started naming itself honestly.
    """
    body = client.get("/api/v1/health").json()
    assert (body["audit_storage"] == "memory") == (body["status"] == "degraded")


def test_action_registry_is_exposed() -> None:
    actions = client.get("/api/v1/actions").json()
    ids = {a["id"] for a in actions}
    assert "rollback_deployment" in ids
    assert "delete_infrastructure" in ids


def test_unregistered_action_cannot_be_evaluated() -> None:
    response = client.post("/api/v1/policy/evaluate", json={"action_id": "rm_minus_rf"})
    assert response.status_code == 404


def test_autonomous_action_executes() -> None:
    verdict = evaluate("restart_service")
    assert verdict["tier"] == "autonomous"
    result = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "restart_service", "verdict": verdict},
    )
    assert result.status_code == 200
    assert result.json()["dry_run"] is True


def test_approval_tier_is_refused_until_approved() -> None:
    verdict = evaluate("rollback_deployment", environment="prod")
    assert verdict["tier"] == "approval"

    refused = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "rollback_deployment", "verdict": verdict},
    )
    assert refused.status_code == 403

    approved = client.post(
        "/api/v1/policy/approve", json={"verdict": verdict, "approver": "preet"}
    ).json()
    allowed = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "rollback_deployment", "verdict": approved},
    )
    assert allowed.status_code == 200


def test_denied_verdict_cannot_be_approved() -> None:
    verdict = evaluate("delete_infrastructure")
    assert verdict["tier"] == "denied"
    response = client.post("/api/v1/policy/approve", json={"verdict": verdict, "approver": "preet"})
    assert response.status_code == 403


def test_verdict_for_another_action_is_rejected() -> None:
    verdict = evaluate("restart_service")
    response = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "clear_cache", "verdict": verdict},
    )
    assert response.status_code == 403


def test_execute_requires_a_verdict_argument() -> None:
    response = client.post("/api/v1/actions/execute", json={"action_id": "restart_service"})
    assert response.status_code == 422, "verdict must be a required field, not optional"


def test_engine_level_bypass_is_impossible() -> None:
    """The guard lives in the engine, not only in the HTTP layer."""
    from app.engines import astra

    with pytest.raises(PolicyViolation):
        astra.execute("restart_service", verdict=None)


def test_policy_denials_are_audited() -> None:
    evaluate("delete_infrastructure", incident_ref="INC-TEST-0001")
    records = client.get("/api/v1/audit", params={"incident_ref": "INC-TEST-0001"}).json()
    assert any(r["kind"] == "policy_evaluation" for r in records)


def test_execution_is_audited_before_and_after() -> None:
    verdict = evaluate("restart_service", incident_ref="INC-TEST-0002")
    client.post(
        "/api/v1/actions/execute",
        json={"action_id": "restart_service", "verdict": verdict},
    )
    kinds = [r["kind"] for r in client.get(
        "/api/v1/audit", params={"incident_ref": "INC-TEST-0002"}
    ).json()]
    assert "execution_attempt" in kinds
    assert "execution_result" in kinds


def test_verification_grades_thresholds() -> None:
    body = client.post(
        "/api/v1/verification/observe",
        json={
            "action_id": "rollback_deployment",
            "observed": {"version": "previous", "error_rate": "0.2%"},
        },
    ).json()
    assert all(check["passed"] for check in body["checks"])


def test_missing_observation_fails_verification() -> None:
    """Absent telemetry means 'don't know', which must never grade as success."""
    body = client.post(
        "/api/v1/verification/observe",
        json={"action_id": "rollback_deployment", "observed": {"version": "previous"}},
    ).json()
    failed = [c for c in body["checks"] if not c["passed"]]
    assert [c["name"] for c in failed] == ["error_rate"]


def test_demo_incident_is_available() -> None:
    """Looked up by id rather than by position: the store also holds incidents
    written by other tests, and ordering is by recency."""
    incidents = client.get("/api/v1/incidents").json()
    assert incidents, "expected at least the seeded demo incident"

    demo = next((i for i in incidents if i["id"] == "INC-2026-0810"), None)
    assert demo is not None, "the seeded demo incident should be present"
    assert demo["impact"]["estimated_users_affected"] == 1240
    assert demo["hypotheses"][0]["evidence"], "hypotheses must cite evidence"


def test_incident_detail_keeps_plan_and_causal_chain() -> None:
    """The detail route once returned an incident with an empty plan and no
    causal chain, and rendered without complaint — an empty section looks like
    'nothing to show' rather than 'we lost it'."""
    incident = client.get("/api/v1/incidents/INC-2026-0810").json()
    assert incident["plan"], "plan must survive the round trip"
    assert incident["causal_chain"], "causal chain must survive the round trip"
    assert incident["transitions"], "timeline must survive the round trip"
    assert all(link["evidence"] for link in incident["causal_chain"])


def test_an_open_incident_colours_the_map() -> None:
    """Telemetry severity is windowed — the worst thing seen in fifteen minutes
    — which is right for a live system and wrong for an entity with an open
    critical incident and no new events. The map read "no data" for every host
    on the board while three incidents sat open.
    """
    from app.api.routes import _overlay_open_incidents
    from app.store import STORE

    incidents = STORE.all()
    if not incidents:
        pytest.skip("no incidents seeded in this configuration")

    keys = {e.key() for i in incidents for e in i.affected_entities}
    if not keys:
        pytest.skip("seeded incidents name no entities")

    snapshot = {"nodes": [{"key": key, "severity": None} for key in keys], "edges": []}
    _overlay_open_incidents(snapshot)

    assert all(node["severity"] is not None for node in snapshot["nodes"])


def test_the_overlay_never_downgrades_live_telemetry() -> None:
    """An entity reporting critical right now must not be softened because the
    incident against it is merely high."""
    from app.api.routes import _overlay_open_incidents
    from app.store import STORE

    incidents = STORE.all()
    if not incidents:
        pytest.skip("no incidents seeded in this configuration")
    key = next((e.key() for i in incidents for e in i.affected_entities), None)
    if key is None:
        pytest.skip("seeded incidents name no entities")

    snapshot = {"nodes": [{"key": key, "severity": "critical"}], "edges": []}
    _overlay_open_incidents(snapshot)
    assert snapshot["nodes"][0]["severity"] == "critical"
