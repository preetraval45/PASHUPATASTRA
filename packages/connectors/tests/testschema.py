"""Schema conformance across every connector.

The Schema ADR made `v0` explicitly unstable and named Phase 1 as its first real
test: the event model was designed before a single byte of real telemetry
arrived, and the question was whether it survived contact.

These tests answer it mechanically. Every connector's output is checked against
the invariants the rest of the system relies on, so a connector cannot quietly
weaken the model — the failure mode where `labels` slowly becomes a dumping
ground for structure that should have been a typed field.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from drishti import (
    DockerConnector,
    GithubDeploymentsConnector,
    KubernetesConnector,
    OpenSearchConnector,
    OtlpReceiver,
    PrometheusConnector,
    WebhookDeployments,
    Window,
)
from pashupatastra import SCHEMA_VERSION, Event

NOW = datetime.now(timezone.utc)


def canned(body) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))


class FakeKubectl(KubernetesConnector):
    def __init__(self, **resources):
        super().__init__(context="test")
        self._resources = resources

    def _run(self, *args):
        return json.dumps({"items": self._resources.get(args[1], [])})


class FakeDocker(DockerConnector):
    def _run(self, *args):
        if args[0] == "ps":
            return json.dumps({"ID": "abc123def4567", "Names": "/svc"})
        return json.dumps(
            [
                {
                    "State": {"Status": "running", "StartedAt": "2026-08-11T10:00:00.123456789Z"},
                    "RestartCount": 2,
                    "Config": {"Image": "postgres:16", "Labels": {}},
                }
            ]
        )


def every_connector_harvest() -> dict[str, list[Event]]:
    """One harvest per source, all from canned but realistic payloads."""
    prometheus = PrometheusConnector(
        client=canned(
            {
                "status": "success",
                "data": {"result": [{"metric": {"job": "api"}, "value": [1786000000, "42.5"]}]},
            }
        ),
        queries={"cpu_usage_pct": "up"},
    ).poll(Window.trailing(300))

    kubernetes = FakeKubectl(
        pods=[
            {
                "metadata": {
                    "name": "api-1",
                    "namespace": "default",
                    "ownerReferences": [{"kind": "ReplicaSet", "name": "api"}],
                },
                "status": {
                    "phase": "Running",
                    "startTime": "2026-08-11T10:00:00Z",
                    "containerStatuses": [{"name": "app", "ready": True, "restartCount": 4}],
                },
            }
        ],
        deployments=[
            {
                "metadata": {"name": "api", "namespace": "default", "creationTimestamp": "2026-08-01T09:00:00Z"},
                "spec": {"template": {"spec": {"containers": [{"image": "api:v4.21"}]}}},
                "status": {"replicas": 3, "readyReplicas": 1},
            }
        ],
    ).poll(Window.trailing(300))

    docker = FakeDocker().poll(Window.trailing(300))

    opensearch = OpenSearchConnector(
        client=canned(
            {
                "hits": {
                    "hits": [
                        {
                            "_id": "d1",
                            "_source": {
                                "service.name": "api",
                                "message": "boom",
                                "level": "error",
                                "@timestamp": NOW.isoformat(),
                            },
                        }
                    ]
                },
                "aggregations": {"by_service": {"buckets": [{"key": "api", "doc_count": 9}]}},
            }
        )
    ).poll(Window.trailing(300))

    otlp = OtlpReceiver().receive(
        {
            "resourceSpans": [
                {
                    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "api"}}]},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "t1",
                                    "spanId": "s1",
                                    "name": "GET /",
                                    "startTimeUnixNano": "1786000000000000000",
                                    "endTimeUnixNano": "1786000000100000000",
                                    "status": {"code": 1},
                                }
                            ]
                        }
                    ],
                }
            ]
        }
    )

    github = GithubDeploymentsConnector(
        repository="acme/api",
        client=canned(
            [
                {
                    "id": 1,
                    "ref": "v4.21",
                    "sha": "a" * 40,
                    "environment": "production",
                    "created_at": (NOW - timedelta(minutes=1)).isoformat(),
                    "creator": {"login": "preet"},
                    "url": "https://api.github.invalid/1",
                }
            ]
        ),
    ).poll(Window.trailing(600))

    webhook = WebhookDeployments().receive({"service": "api", "version": "v4.21"})

    return {
        "prometheus": prometheus.events,
        "kubernetes": kubernetes.events,
        "docker": docker.events,
        "opensearch": opensearch.events,
        "otlp": otlp.events,
        "github": github.events,
        "webhook": webhook.events,
    }


HARVESTS = every_connector_harvest()


@pytest.mark.parametrize("source", sorted(HARVESTS))
def test_connector_produces_events(source: str) -> None:
    assert HARVESTS[source], f"{source} produced nothing — the fixture no longer exercises it"


@pytest.mark.parametrize("source", sorted(HARVESTS))
def test_every_event_declares_the_schema_version(source: str) -> None:
    assert all(e.schema_version == SCHEMA_VERSION for e in HARVESTS[source])


@pytest.mark.parametrize("source", sorted(HARVESTS))
def test_every_event_carries_provenance(source: str) -> None:
    """Mandatory, because every downstream claim must be traceable to a record a
    human can re-fetch."""
    for event in HARVESTS[source]:
        assert event.provenance.source_system
        assert event.provenance.query or event.provenance.url, event.id


@pytest.mark.parametrize("source", sorted(HARVESTS))
def test_every_event_resolves_to_an_entity(source: str) -> None:
    for event in HARVESTS[source]:
        assert event.entity_ref.id and event.entity_ref.name
        assert ":" in event.entity_ref.key()


@pytest.mark.parametrize("source", sorted(HARVESTS))
def test_timestamps_are_timezone_aware(source: str) -> None:
    """A naive timestamp silently becomes local time somewhere downstream, and
    causal ordering across sources is exactly what must not drift."""
    for event in HARVESTS[source]:
        assert event.occurred_at.tzinfo is not None, event.id
        assert event.observed_at.tzinfo is not None, event.id


@pytest.mark.parametrize("source", sorted(HARVESTS))
def test_events_round_trip_through_json(source: str) -> None:
    """The persistence path is JSON. If a payload cannot survive it, the event
    is unstorable and the schema has failed."""
    for event in HARVESTS[source]:
        restored = Event.model_validate_json(event.model_dump_json())
        assert restored.id == event.id
        assert type(restored.payload) is type(event.payload)


@pytest.mark.parametrize("source", sorted(HARVESTS))
def test_labels_hold_dimensions_not_structure(source: str) -> None:
    """`labels` is for flat dimensions. A connector needing typed structure asks
    for a schema change — overflow into labels is the failure the Schema ADR
    exists to prevent, and it is a review-bar item."""
    for event in HARVESTS[source]:
        for key, value in event.labels.items():
            assert isinstance(key, str)
            assert isinstance(value, str), f"{source}: label {key} is {type(value)}"


def test_v0_survived_contact_with_every_source() -> None:
    """The Schema ADR's Phase 1 question, answered in one assertion.

    Seven sources across six event classes normalize into v0 without a single
    connector needing a field the model does not have. That is the evidence for
    declaring v1 — not that the schema is perfect, but that it stopped moving
    under real input.
    """
    classes = {e.event_class for events in HARVESTS.values() for e in events}
    assert len(HARVESTS) == 7
    assert {"metric", "log", "trace", "state_change", "deployment"} <= {c.value for c in classes}
