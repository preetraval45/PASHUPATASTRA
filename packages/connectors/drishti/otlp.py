"""OpenTelemetry — OTLP/HTTP JSON normalization.

Traces arrive by **push**, not poll, so this is a `Receiver` rather than a
`Connector`. The distinction is real and worth keeping: a poller controls its own
window and can be re-run, while a receiver is handed whatever the sender chose to
emit and gets one chance at it. That difference drives two rules here:

  * Normalization never raises. A malformed span must not reject the whole batch,
    because the sender will not retry and the rest of the batch is still evidence.
  * Nothing is inferred from absence. A missing parent span means the trace is
    incomplete, not that the span is a root — treating it as a root would invent
    a service entry point that does not exist.

Traces are the strongest edge source in the system: a span with a parent is
direct evidence that one service called another. That is why `service_hops` is
reconstructed from the actual span tree rather than from span ordering, which
concurrency makes meaningless.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pashupatastra import (
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Provenance,
    QuarantinedEvent,
    Severity,
)
from pashupatastra.events import TracePayload
from pashupatastra.topology import Edge

from .base import Harvest

# OTLP status codes: 0 unset, 1 ok, 2 error.
_ERROR_STATUS = 2

# Span kinds. 2 = SERVER, 3 = CLIENT; a client span names the caller's side of a
# call, which is what makes the parent→child pair a dependency rather than an
# internal function call.
_SPAN_KIND_INTERNAL = 1


class OtlpReceiver:
    """Normalizes an OTLP/HTTP JSON trace export into events and edges."""

    name = "opentelemetry"
    version = "0.1.0"

    def receive(self, payload: dict) -> Harvest:
        harvest = Harvest()
        observed = datetime.now().astimezone()

        for resource_spans in payload.get("resourceSpans", []) or []:
            service = _service_name(resource_spans.get("resource", {}))
            if not service:
                harvest.quarantined.append(
                    QuarantinedEvent(
                        raw={"resource": resource_spans.get("resource", {})},
                        source=self.name,
                        reason="resource has no service.name attribute",
                        observed_at=observed,
                    )
                )
                continue

            for scope_spans in resource_spans.get("scopeSpans", []) or []:
                for span in scope_spans.get("spans", []) or []:
                    try:
                        self._span(span, service, harvest, observed)
                    except Exception as exc:
                        # One bad span must not cost the batch; the sender will
                        # not retry.
                        harvest.quarantined.append(
                            QuarantinedEvent(
                                raw={"span": span},
                                source=self.name,
                                reason=f"malformed span: {type(exc).__name__}: {exc}",
                                observed_at=observed,
                            )
                        )

        self._edges_from_spans(harvest)
        return harvest

    def _span(self, span: dict, service: str, harvest: Harvest, observed: datetime) -> None:
        # A span with no trace or span ID cannot join the span tree, so it can
        # neither be correlated nor produce an edge. Checked explicitly because
        # str(None) is a perfectly valid string and would sail through typing.
        trace_id, span_id = span.get("traceId"), span.get("spanId")
        if not isinstance(trace_id, str) or not trace_id:
            raise ValueError("span has no traceId")
        if not isinstance(span_id, str) or not span_id:
            raise ValueError("span has no spanId")

        start = _nanos(span.get("startTimeUnixNano"))
        end = _nanos(span.get("endTimeUnixNano"))
        duration_ms = (end - start).total_seconds() * 1000 if start and end else 0.0
        status_code = int((span.get("status") or {}).get("code", 0) or 0)

        ref = EntityRef(kind=EntityKind.SERVICE, id=service, name=service)
        harvest.events.append(
            Event(
                event_class=EventClass.TRACE,
                source=self.name,
                source_version=self.version,
                occurred_at=start or observed,
                observed_at=observed,
                entity_ref=ref,
                severity=Severity.WARNING if status_code == _ERROR_STATUS else None,
                payload=TracePayload(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=str(span.get("parentSpanId") or "") or None,
                    duration_ms=round(duration_ms, 3),
                    status="error" if status_code == _ERROR_STATUS else "ok",
                    # Filled by _edges_from_spans once the whole batch is known:
                    # a hop list needs the span tree, which one span cannot see.
                    service_hops=[],
                ),
                provenance=Provenance(
                    source_system="opentelemetry",
                    query=f"trace {trace_id}",
                ),
                labels={
                    "span_name": str(span.get("name", "")),
                    "span_kind": str(span.get("kind", _SPAN_KIND_INTERNAL)),
                    **_attributes(span.get("attributes", [])),
                },
            )
        )

    def _edges_from_spans(self, harvest: Harvest) -> None:
        """Reconstruct caller→callee from the span tree.

        Ordering within a batch says nothing — concurrent spans arrive in any
        order — so the parent link is the only trustworthy signal.
        """
        service_by_span: dict[str, str] = {}
        for event in harvest.events:
            payload = event.payload
            if isinstance(payload, TracePayload) and payload.span_id:
                service_by_span[payload.span_id] = event.entity_ref.name

        seen: set[tuple[str, str]] = set()
        for event in harvest.events:
            payload = event.payload
            if not isinstance(payload, TracePayload) or not payload.parent_span_id:
                continue

            caller = service_by_span.get(payload.parent_span_id)
            if caller is None:
                # Parent is in another batch or was dropped. The trace is
                # incomplete; inventing a root here would fabricate an entry
                # point that does not exist.
                continue

            callee = event.entity_ref.name
            if caller == callee:
                continue  # internal span, not a service dependency

            payload.service_hops = [caller, callee]
            if (caller, callee) not in seen:
                seen.add((caller, callee))
                harvest.edges.append(
                    Edge(
                        source=f"{EntityKind.SERVICE.value}:{caller}",
                        target=f"{EntityKind.SERVICE.value}:{callee}",
                        kind="depends_on",
                    )
                )


def _service_name(resource: dict) -> str | None:
    for attribute in resource.get("attributes", []) or []:
        if attribute.get("key") == "service.name":
            return _value(attribute.get("value", {}))
    return None


def _attributes(attributes: list) -> dict[str, str]:
    out: dict[str, str] = {}
    for attribute in attributes or []:
        key = attribute.get("key")
        value = _value(attribute.get("value", {}))
        if key and value is not None:
            out[str(key)] = str(value)
    return out


def _value(value: dict):
    for field in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if field in value:
            return value[field]
    return None


def _nanos(value) -> datetime | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1_000_000_000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
