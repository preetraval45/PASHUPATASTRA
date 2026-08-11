"""CI/CD deployment events — the highest-yield causal signal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from drishti import GithubDeploymentsConnector, WebhookDeployments, Window
from pashupatastra import EventClass

NOW = datetime.now(timezone.utc)


def deployment(ref: str, minutes_ago: int = 1, environment: str = "production", **extra) -> dict:
    return {
        "id": 1,
        "ref": ref,
        "sha": "a" * 40,
        "environment": environment,
        "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "creator": {"login": "preet"},
        "url": "https://api.github.invalid/deployments/1",
        **extra,
    }


def connector(deployments: list[dict]) -> GithubDeploymentsConnector:
    return GithubDeploymentsConnector(
        repository="acme/checkout",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=deployments))
        ),
    )


def test_deployment_becomes_a_first_class_event() -> None:
    harvest = connector([deployment("v4.21")]).poll(Window.trailing(600))
    event = harvest.events[0]
    assert event.event_class is EventClass.DEPLOYMENT
    assert event.payload.version == "v4.21"
    assert event.payload.actor == "preet"


def test_a_deployment_is_not_itself_a_problem() -> None:
    """Severity stays unset so nothing reads 'a deploy happened' as 'a deploy
    broke something' — that inference belongs to correlation."""
    harvest = connector([deployment("v4.21")]).poll(Window.trailing(600))
    assert harvest.events[0].severity is None


def test_previous_version_is_recorded_across_polls() -> None:
    c = connector([deployment("v4.20")])
    c.poll(Window.trailing(600))

    c._client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=[deployment("v4.21")])
        )
    )
    harvest = c.poll(Window.trailing(600))
    assert harvest.events[0].payload.previous_version == "v4.20"


def test_first_deployment_has_no_invented_predecessor() -> None:
    """Inventing a 'from' version would put a fabricated fact in front of a
    root-cause analysis."""
    harvest = connector([deployment("v4.21")]).poll(Window.trailing(600))
    assert harvest.events[0].payload.previous_version is None


def test_deployments_outside_the_window_are_ignored() -> None:
    harvest = connector([deployment("v3.0", minutes_ago=600)]).poll(Window.trailing(300))
    assert harvest.events == []


def test_non_production_environments_are_filtered() -> None:
    harvest = connector([deployment("v4.21", environment="staging")]).poll(Window.trailing(600))
    assert harvest.events == []


def test_service_comes_from_the_payload_when_present() -> None:
    harvest = connector([deployment("v4.21", payload={"service": "checkout-api"})]).poll(
        Window.trailing(600)
    )
    assert harvest.events[0].payload.service == "checkout-api"


def test_service_falls_back_to_the_repository_name() -> None:
    harvest = connector([deployment("v4.21")]).poll(Window.trailing(600))
    assert harvest.events[0].payload.service == "checkout"


def test_api_failure_is_reported_not_raised() -> None:
    broken = GithubDeploymentsConnector(
        repository="acme/checkout",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(401, text="bad credentials"))
        ),
    )
    harvest = broken.poll(Window.trailing(600))
    assert harvest.events == []
    assert not harvest.healthy


def test_webhook_normalizes_a_pushed_deployment() -> None:
    harvest = WebhookDeployments().receive(
        {"service": "checkout-api", "version": "v4.21", "previous_version": "v4.20", "actor": "ci"}
    )
    assert harvest.events[0].payload.previous_version == "v4.20"


def test_webhook_without_required_fields_is_rejected_loudly() -> None:
    harvest = WebhookDeployments().receive({"service": "checkout-api"})
    assert harvest.events == []
    assert not harvest.healthy
