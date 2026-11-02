"""Excessive agency: no path reaches an executor without a verdict Dharma recorded.

Rule 2 says every executable action is routed through policy evaluation. The routes that act on a
verdict take it from the request body, so "routed through" has to mean "issued here", not "shaped
like a verdict": a client that writes `"tier": "autonomous"` into the JSON has not been evaluated.
Each route is checked with forged and altered verdicts, and the check is that nothing was attempted
— no execution record in the audit trail — not merely that the response was an error.

The structural half pins the shape: only Astra may build an executor, and every route that accepts
a verdict is one of the four checked here. A new route that takes a verdict fails the last test
until it is added, and with it, until it checks the seal.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pashupatastra.dharma import Tier, Verdict

from app.engines.audit import AUDIT, AuditKind
from app.engines.seal import is_sealed, seal
from app.main import app

client = TestClient(app)
APP = Path(__file__).resolve().parents[1] / "app"


def attempts() -> int:
    return len(AUDIT.records(limit=100_000, kind=AuditKind.EXECUTION_ATTEMPT))


def issued(action_id: str = "restart_service", **context: object) -> dict:
    response = client.post("/api/v1/policy/evaluate", json={"action_id": action_id, **context})
    assert response.status_code == 200, response.text
    return response.json()


def forged(action_id: str = "restart_service") -> dict:
    """What a caller can write without ever asking Dharma."""
    return Verdict(
        action_id=action_id,
        incident_ref=None,
        base_risk=0,
        adjustments=[],
        effective_risk=0,
        tier=Tier.AUTONOMOUS,
        required_approvers=[],
        granted_by="human:me",
        expires_at=datetime.now().astimezone() + timedelta(minutes=15),
    ).model_dump(mode="json")


def altered(verdict: dict, **changes: object) -> dict:
    return {**verdict, **changes}


def refused_without_attempt(path: str, body: dict) -> None:
    before = attempts()
    response = client.post(path, json=body)
    assert response.status_code == 403, response.text
    assert attempts() == before, f"{path} wrote an execution attempt for a verdict it refused"


# --- the four routes that act on a verdict ----------------------------------------------------------


def test_a_forged_verdict_does_not_execute() -> None:
    refused_without_attempt(
        "/api/v1/actions/execute", {"action_id": "restart_service", "verdict": forged()}
    )


def test_a_forged_verdict_does_not_start_a_remediation_or_its_rollback() -> None:
    """The loop rolls back whatever its runner fails on, so a refusal inside the runner would turn
    a forged request into a real, separately authorised undo. It must stop before the loop."""
    refused_without_attempt(
        "/api/v1/actions/remediate",
        {
            "action_id": "restart_service",
            "verdict": forged(),
            "params": {"namespace": "default", "deployment": "web"},
        },
    )


def test_raising_the_tier_of_an_issued_verdict_breaks_its_seal() -> None:
    verdict = issued("rollback_deployment", environment="prod")
    assert verdict["tier"] == "approval"
    refused_without_attempt(
        "/api/v1/actions/execute",
        {"action_id": "rollback_deployment", "verdict": altered(verdict, tier="autonomous")},
    )


def test_writing_in_an_approver_breaks_the_seal() -> None:
    verdict = issued("rollback_deployment", environment="prod")
    refused_without_attempt(
        "/api/v1/actions/execute",
        {"action_id": "rollback_deployment", "verdict": altered(verdict, granted_by="human:me")},
    )


def test_extending_the_expiry_breaks_the_seal() -> None:
    verdict = issued()
    later = (datetime.now().astimezone() + timedelta(days=365)).isoformat()
    refused_without_attempt(
        "/api/v1/actions/execute",
        {"action_id": "restart_service", "verdict": altered(verdict, expires_at=later)},
    )


@pytest.mark.parametrize("route", ["/api/v1/policy/approve", "/api/v1/policy/deny"])
def test_a_forged_verdict_cannot_be_approved_or_denied(route: str) -> None:
    """A forged approval tier would otherwise be laundered into a sealed, granted verdict."""
    body = {"verdict": forged("rollback_deployment"), "approver": "visitor", "reason": "test"}
    before = len(AUDIT.records(limit=100_000, kind=AuditKind.APPROVAL))
    assert client.post(route, json=body).status_code == 403
    assert len(AUDIT.records(limit=100_000, kind=AuditKind.APPROVAL)) == before


def test_an_issued_verdict_still_executes_after_the_round_trip() -> None:
    """The seal must survive JSON, or the check would refuse everything and prove nothing."""
    verdict = issued()
    assert verdict["tier"] == "autonomous" and verdict["seal"]
    before = attempts()
    response = client.post(
        "/api/v1/actions/execute", json={"action_id": "restart_service", "verdict": verdict}
    )
    assert response.status_code == 200, response.text
    assert attempts() == before + 1


def test_an_approval_reseals_what_it_changed() -> None:
    verdict = issued("rollback_deployment", environment="prod")
    approved = client.post(
        "/api/v1/policy/approve", json={"verdict": verdict, "approver": "operator"}
    ).json()
    assert approved["granted_by"] == "human:operator"
    assert is_sealed(Verdict.model_validate(approved))
    assert approved["seal"] != verdict["seal"]


def test_a_preview_is_never_sealed() -> None:
    preview = client.post("/api/v1/policy/preview", json={"action_id": "restart_service"}).json()
    assert preview.get("seal") is None
    refused_without_attempt(
        "/api/v1/actions/execute", {"action_id": "restart_service", "verdict": preview}
    )


def test_display_fields_are_outside_the_seal() -> None:
    """Older dashboards drop `tier_reasons`; dropping it changes nothing about what may run."""
    verdict = Verdict.model_validate(issued())
    verdict.tier_reasons = []
    verdict.adjustments = []
    assert is_sealed(verdict)
    verdict.effective_risk += 1
    assert not is_sealed(verdict)
    assert is_sealed(seal(verdict))


# --- the shape ---------------------------------------------------------------------------------------


def _reaches(path: Path) -> set[str]:
    """What a module takes from the executors, and whether it asks Astra for the live one."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] == "executors":
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if name == "live_executor":
                found.add(name)
    return found


def test_only_astra_builds_an_executor() -> None:
    """The loop may hold the live router, for reading state before and after an action, but only
    through Astra and only after its verdict has been checked."""
    allowed = {
        "engines/astra.py": {"KubernetesExecutor", "NotifyExecutor", "Router", "live_executor"},
        "engines/loop.py": {"live_executor"},
    }
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        if rel == "engines/executors.py":
            continue
        reached = _reaches(path)
        assert reached <= allowed.get(rel, set()), f"{rel} reaches an executor: {sorted(reached)}"
    assert _reaches(APP / "engines/astra.py") == allowed["engines/astra.py"], "the check found nothing"


def _mentions_verdict(schema: object, components: dict, seen: set[str]) -> bool:
    """Whether a request body's schema holds a Verdict anywhere, following references."""
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if ref is not None:
            name = ref.rsplit("/", 1)[-1]
            if name == "Verdict":
                return True
            if name in seen:
                return False
            seen.add(name)
            return _mentions_verdict(components.get(name), components, seen)
        return any(_mentions_verdict(value, components, seen) for value in schema.values())
    if isinstance(schema, list):
        return any(_mentions_verdict(value, components, seen) for value in schema)
    return False


def test_every_route_that_accepts_a_verdict_is_checked_here() -> None:
    checked = {
        "/api/v1/actions/execute",
        "/api/v1/actions/remediate",
        "/api/v1/policy/approve",
        "/api/v1/policy/deny",
    }
    spec = app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    taking = {
        path
        for path, methods in spec["paths"].items()
        for operation in methods.values()
        if _mentions_verdict(operation.get("requestBody"), components, set())
    }
    assert taking == checked, f"routes accepting a verdict changed: {sorted(taking ^ checked)}"
