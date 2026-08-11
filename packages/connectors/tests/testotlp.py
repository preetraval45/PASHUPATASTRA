"""OTLP trace normalization.

Traces are the strongest edge source in the system, so the tests concentrate on
the two ways that strength could be misused: fabricating a dependency that was
never observed, and losing a whole batch to one bad span.
"""

from __future__ import annotations

from drishti import OtlpReceiver
from pashupatastra import EventClass, Severity
from pashupatastra.events import TracePayload


def span(
    span_id: str,
    service: str,
    parent: str | None = None,
    status: int = 1,
    name: str = "GET /checkout",
) -> tuple[str, dict]:
    return service, {
        "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
        "spanId": span_id,
        "parentSpanId": parent or "",
        "name": name,
        "kind": 2,
        "startTimeUnixNano": "1786000000000000000",
        "endTimeUnixNano": "1786000000180000000",
        "status": {"code": status},
        "attributes": [{"key": "http.method", "value": {"stringValue": "GET"}}],
    }


def payload(*spans: tuple[str, dict]) -> dict:
    by_service: dict[str, list[dict]] = {}
    for service, s in spans:
        by_service.setdefault(service, []).append(s)
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": svc}}]},
                "scopeSpans": [{"spans": items}],
            }
            for svc, items in by_service.items()
        ]
    }


def test_span_becomes_a_trace_event() -> None:
    harvest = OtlpReceiver().receive(payload(span("aaa", "frontend")))
    event = harvest.events[0]
    assert event.event_class is EventClass.TRACE
    assert event.entity_ref.name == "frontend"
    assert event.payload.duration_ms == 180.0


def test_parent_child_across_services_becomes_an_edge() -> None:
    harvest = OtlpReceiver().receive(
        payload(span("aaa", "frontend"), span("bbb", "checkout", parent="aaa"))
    )
    assert [(e.source, e.target) for e in harvest.edges] == [
        ("service:frontend", "service:checkout")
    ]


def test_service_hops_are_filled_from_the_span_tree() -> None:
    """Not from ordering — concurrent spans arrive in any order."""
    harvest = OtlpReceiver().receive(
        payload(span("bbb", "checkout", parent="aaa"), span("aaa", "frontend"))
    )
    child = next(
        e for e in harvest.events if isinstance(e.payload, TracePayload) and e.payload.parent_span_id
    )
    assert child.payload.service_hops == ["frontend", "checkout"]


def test_same_service_parent_is_not_a_dependency() -> None:
    """An internal span is a function call, not a service dependency."""
    harvest = OtlpReceiver().receive(
        payload(span("aaa", "checkout"), span("bbb", "checkout", parent="aaa"))
    )
    assert harvest.edges == []


def test_missing_parent_does_not_become_a_root() -> None:
    """The trace is incomplete. Treating the span as a root would invent an
    entry point that does not exist."""
    harvest = OtlpReceiver().receive(payload(span("bbb", "checkout", parent="missing")))
    assert harvest.edges == []
    assert harvest.events, "the span itself is still evidence"


def test_repeated_calls_produce_one_edge() -> None:
    harvest = OtlpReceiver().receive(
        payload(
            span("aaa", "frontend"),
            span("bbb", "checkout", parent="aaa"),
            span("ccc", "checkout", parent="aaa"),
        )
    )
    assert len(harvest.edges) == 1


def test_error_status_is_flagged() -> None:
    harvest = OtlpReceiver().receive(payload(span("aaa", "checkout", status=2)))
    assert harvest.events[0].severity is Severity.WARNING
    assert harvest.events[0].payload.status == "error"


def test_resource_without_service_name_is_quarantined() -> None:
    harvest = OtlpReceiver().receive(
        {"resourceSpans": [{"resource": {"attributes": []}, "scopeSpans": []}]}
    )
    assert harvest.events == []
    assert "service.name" in harvest.quarantined[0].reason


def test_one_malformed_span_does_not_lose_the_batch() -> None:
    """The sender will not retry, so the rest of the batch must survive."""
    service, good = span("aaa", "frontend")
    body = payload((service, good))
    body["resourceSpans"][0]["scopeSpans"][0]["spans"].append({"traceId": None, "spanId": None})

    harvest = OtlpReceiver().receive(body)
    assert len(harvest.events) == 1
    assert len(harvest.quarantined) == 1


def test_attributes_are_carried_as_labels() -> None:
    harvest = OtlpReceiver().receive(payload(span("aaa", "frontend")))
    assert harvest.events[0].labels["http.method"] == "GET"
    assert harvest.events[0].labels["span_name"] == "GET /checkout"


def test_empty_payload_is_not_an_error() -> None:
    harvest = OtlpReceiver().receive({})
    assert harvest.healthy
    assert harvest.events == []
