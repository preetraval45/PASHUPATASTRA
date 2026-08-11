"""Prometheus connector tests.

Normalization is tested against canned API responses; the live test runs only
when the compose stack is up.
"""

from __future__ import annotations

import httpx
import pytest
from drishti import PrometheusConnector, Window
from pashupatastra import EntityKind, EventClass, Severity


def canned(results: list[dict]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": {"result": results}})

    return httpx.Client(transport=httpx.MockTransport(handler))


def connector(results: list[dict], **kwargs) -> PrometheusConnector:
    return PrometheusConnector(client=canned(results), queries={"up": "up"}, **kwargs)


def test_series_becomes_a_normalized_event() -> None:
    harvest = connector(
        [{"metric": {"job": "checkout-api", "instance": "10.0.0.4:8000"}, "value": [1754900000, "1"]}]
    ).poll(Window.trailing(300))

    assert len(harvest.events) == 1
    event = harvest.events[0]
    assert event.event_class is EventClass.METRIC
    assert event.entity_ref.name == "checkout-api"
    assert event.entity_ref.kind is EntityKind.SERVICE
    assert event.payload.value == 1.0


def test_provenance_is_always_stamped() -> None:
    harvest = connector([{"metric": {"job": "api"}, "value": [1754900000, "1"]}]).poll(
        Window.trailing(300)
    )
    provenance = harvest.events[0].provenance
    assert provenance.source_system == "prometheus"
    assert provenance.query == "up"
    assert provenance.url


def test_entity_label_preference_order() -> None:
    """`service` wins over `instance` — the more specific identity, not the host."""
    harvest = connector(
        [{"metric": {"service": "checkout", "instance": "10.0.0.4:8000"}, "value": [1, "1"]}]
    ).poll(Window.trailing(60))
    assert harvest.events[0].entity_ref.name == "checkout"


def test_unidentifiable_series_is_quarantined_not_dropped() -> None:
    harvest = connector([{"metric": {"foo": "bar"}, "value": [1, "1"]}]).poll(Window.trailing(60))
    assert harvest.events == []
    assert len(harvest.quarantined) == 1
    assert "entity" in harvest.quarantined[0].reason


def test_nan_is_absence_not_zero() -> None:
    """A NaN recorded as 0 would invent a healthy signal out of missing data."""
    harvest = connector([{"metric": {"job": "api"}, "value": [1, "not-a-number"]}]).poll(
        Window.trailing(60)
    )
    assert harvest.events == []
    assert harvest.quarantined == []


def test_target_down_is_critical() -> None:
    harvest = connector([{"metric": {"job": "api"}, "value": [1, "0"]}]).poll(Window.trailing(60))
    assert harvest.events[0].severity is Severity.CRITICAL


def test_query_failure_is_reported_not_swallowed() -> None:
    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    harvest = PrometheusConnector(
        client=httpx.Client(transport=httpx.MockTransport(failing)), queries={"up": "up"}
    ).poll(Window.trailing(60))

    assert harvest.events == []
    assert not harvest.healthy
    assert "up:" in harvest.errors[0]


def test_window_start_is_exclusive_of_the_previous_end() -> None:
    first = Window.trailing(60)
    second = Window(start=first.end, end=first.end)
    assert second.start >= first.end, "consecutive polls must not overlap"


@pytest.mark.skipif(
    not PrometheusConnector().check(), reason="local Prometheus not running"
)
def test_against_live_prometheus() -> None:
    harvest = PrometheusConnector(queries={"up": "up"}).poll(Window.trailing(300))
    assert harvest.healthy
    assert harvest.events, "expected at least Prometheus scraping itself"
    assert all(e.provenance.query for e in harvest.events)
