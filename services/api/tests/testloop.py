"""The remediation loop wired to the service.

The sequencing itself is covered in packages/core. What is only testable here is
the seam: that a rollback gets its own Dharma verdict rather than reusing the one
issued for the action it is undoing, that dry-run cannot report success, and that
the outcome reaches memory either way.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pashupatastra import Environment, Tier, Verdict
from pashupatastra.learning import Prediction
from pashupatastra.observation import WindowObserver
from pashupatastra.remediation import Disposition

from app.engines import loop as loop_engine
from app.main import app

NOW = datetime(2026, 8, 18, 16, 0, 0).astimezone()


@pytest.fixture(autouse=True)
def fresh_state():
    """The loop's history and memory are process-wide, like the audit log."""
    loop_engine.HISTORY = type(loop_engine.HISTORY)()
    loop_engine.MEMORY = type(loop_engine.MEMORY)()
    yield


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def instant() -> WindowObserver:
    """Advances the clock only on sleep, so a window closes in microseconds."""
    clock = Clock()
    return WindowObserver(clock=clock, sleep=clock.sleep)


def a_verdict(action_id: str = "rollback_deployment") -> Verdict:
    return Verdict(
        action_id=action_id,
        incident_ref="INC-1",
        base_risk=10,
        adjustments=[],
        effective_risk=10,
        tier=Tier.AUTONOMOUS,
        required_approvers=[],
        expires_at=datetime.now().astimezone() + timedelta(minutes=15),
    )


def run(action_id: str = "rollback_deployment", **kwargs):
    params = kwargs.pop("params", {"namespace": "default", "deployment": "web"})
    verdict = kwargs.pop("verdict", None) or a_verdict(action_id)
    return loop_engine.remediate(
        action_id, verdict, params=params, observer=instant(), **kwargs
    )


# --- the policy boundary ------------------------------------------------------


def test_a_rollback_does_not_reuse_the_verdict_for_the_action_it_undoes() -> None:
    """A rollback is an execution, so it needs its own authorisation.

    require_verdict binds a verdict to one action ID, so reusing it would fail
    outright today. This asserts the loop issues a separate verdict rather than
    merely depending on that check to catch it.
    """
    issued: list[str] = []
    original = loop_engine.evaluate

    def spy(action, context, incident_ref=None, agent_risk_limit=None):
        issued.append(action.id)
        return original(
            action, context, incident_ref=incident_ref, agent_risk_limit=agent_risk_limit
        )

    loop_engine.evaluate = spy
    try:
        run(incident_ref="INC-1")
    finally:
        loop_engine.evaluate = original

    # Dry-run cannot verify, so the loop rolls back — and that rollback is
    # authorised on its own rather than riding the original verdict.
    assert "redeploy_version" in issued
    assert "rollback_deployment" not in issued, "the supplied verdict was reused"


def test_the_supplied_verdict_must_match_the_requested_action() -> None:
    with pytest.raises(Exception) as caught:
        run("restart_service", verdict=a_verdict("scale_service"), incident_ref="INC-1")
    assert "verdict is for" in str(caught.value)


# --- dry-run cannot report success -------------------------------------------


def test_dry_run_cannot_verify_and_so_cannot_resolve() -> None:
    """Nothing was changed, so there is no post-state to read. Passing here would
    let a dry-run close an incident."""
    result, _ = run(incident_ref="INC-1")
    assert result.disposition is not Disposition.RESOLVED


# --- learning happens either way ---------------------------------------------


def test_a_failed_loop_is_still_written_to_memory() -> None:
    result, learned = run(
        incident_ref="INC-1",
        summary="checkout latency after deploy",
        entities=["service:checkout"],
    )
    assert result.disposition is not Disposition.RESOLVED
    assert learned
    assert len(loop_engine.HISTORY) >= 1

    recalled = loop_engine.MEMORY.recall(
        "default", "checkout latency", entities={"service:checkout"}
    )
    assert len(recalled) == 1
    assert recalled[0].record.outcome is not None
    assert recalled[0].record.outcome.warning is not None


def test_an_execution_feeds_the_novelty_penalty_for_the_next_one() -> None:
    """The point of wiring history in: a second attempt is no longer novel."""
    now = datetime.now().astimezone()
    before = loop_engine.HISTORY.familiarity("rollback_deployment", Environment.DEV, now)
    run(incident_ref="INC-1")
    after = loop_engine.HISTORY.familiarity("rollback_deployment", Environment.DEV, now)

    assert before.value == "novel"
    assert after.value != "novel"


def test_no_incident_ref_means_nothing_is_filed() -> None:
    """A memory with nothing to file it against would be unrecallable anyway."""
    _, learned = run()
    assert not learned


def test_a_blast_radius_prediction_is_graded_when_an_observation_is_given() -> None:
    run(
        incident_ref="INC-1",
        predicted=Prediction(entities=1, users=10),
        observed=Prediction(entities=6, users=900),
    )
    error = loop_engine.HISTORY.estimation_error()
    assert error.samples == 1
    assert not error.calibrated, "under-estimated by 5 entities"


# --- the route ----------------------------------------------------------------


def test_the_route_reports_the_disposition_rather_than_a_bare_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/actions/remediate",
        json={
            "action_id": "rollback_deployment",
            "verdict": a_verdict().model_dump(mode="json"),
            "params": {"namespace": "default", "deployment": "web"},
            "incident_ref": "INC-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["disposition"] in {d.value for d in Disposition}
    assert body["verified"] is False


def test_the_route_refuses_a_mismatched_verdict() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/actions/remediate",
        json={
            "action_id": "restart_service",
            "verdict": a_verdict("scale_service").model_dump(mode="json"),
        },
    )
    assert response.status_code == 403


def test_the_route_404s_on_an_unregistered_action() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/actions/remediate",
        json={
            "action_id": "rm_minus_rf",
            "verdict": a_verdict("rm_minus_rf").model_dump(mode="json"),
        },
    )
    assert response.status_code == 404
