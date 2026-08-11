"""OpenSearch / Elasticsearch connector — logs.

Logs are the noisiest source in the system and the one most likely to mislead.
Two consequences shape this connector:

**Logs are attacker-influenced input.** Anyone who can write a log line can put
text in front of the reasoning engine. That text is quoted data and never an
instruction (docs/SECURITY.md, T1). Nothing here interprets a message; it is
carried verbatim into a payload field and the reasoner is responsible for
treating it as evidence rather than direction.

**Volume, not signal, is the default.** A million INFO lines say nothing an
incident needs. This connector queries for error-level and above by default and
aggregates rather than streaming every line — the reasoning layer needs to know
that errors rose tenfold on one service, not to read them all.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from pashupatastra import (
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Provenance,
    QuarantinedEvent,
    Severity,
)
from pashupatastra.events import LogPayload, MetricPayload

from .base import Connector, Harvest, Window

# Field names differ per shipper; these are the common conventions, in order.
_SERVICE_FIELDS = ("service.name", "service", "kubernetes.labels.app", "container.name", "host.name")
_MESSAGE_FIELDS = ("message", "log", "msg")
_LEVEL_FIELDS = ("level", "log.level", "severity")

_LEVEL_SEVERITY = {
    "fatal": Severity.CRITICAL,
    "critical": Severity.CRITICAL,
    "error": Severity.CRITICAL,
    "err": Severity.CRITICAL,
    "warn": Severity.WARNING,
    "warning": Severity.WARNING,
}


class OpenSearchConnector(Connector):
    name = "opensearch"

    def __init__(
        self,
        base_url: str = "http://localhost:9200",
        index: str = "logs-*",
        levels: tuple[str, ...] = ("error", "err", "fatal", "critical"),
        sample_size: int = 25,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.index = index
        self.levels = levels
        self.sample_size = sample_size
        """How many individual lines to carry through. The count matters more
        than the lines; a sample exists so a human can read what it looked
        like, not so the reasoner can grep."""
        self.timeout = timeout
        self._client = client

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _search(self, body: dict) -> dict:
        response = self._http().post(
            f"{self.base_url}/{self.index}/_search",
            json=body,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def poll(self, window: Window) -> Harvest:
        harvest = Harvest()
        observed = datetime.now().astimezone()

        query = {
            "size": self.sample_size,
            "sort": [{"@timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gt": window.start.isoformat(),
                                    "lte": window.end.isoformat(),
                                }
                            }
                        },
                        {"terms": {"level": list(self.levels)}},
                    ]
                }
            },
            # The aggregate is the point: "errors on checkout-api went from 3 to
            # 400" is a signal; four hundred stack traces are not.
            "aggs": {"by_service": {"terms": {"field": "service.name", "size": 20}}},
        }

        try:
            body = self._search(query)
        except Exception as exc:
            harvest.errors.append(f"{self.name}: {type(exc).__name__}: {exc}")
            return harvest

        window_seconds = int((window.end - window.start).total_seconds())

        for bucket in body.get("aggregations", {}).get("by_service", {}).get("buckets", []):
            service = bucket.get("key")
            if not service:
                continue
            ref = EntityRef(kind=EntityKind.SERVICE, id=str(service), name=str(service))
            count = int(bucket.get("doc_count", 0))
            harvest.events.append(
                Event(
                    event_class=EventClass.METRIC,
                    source=self.name,
                    source_version=self.version,
                    occurred_at=window.end,
                    observed_at=observed,
                    entity_ref=ref,
                    severity=Severity.WARNING if count else None,
                    payload=MetricPayload(
                        name="log_error_count",
                        value=float(count),
                        unit="count",
                        window_seconds=window_seconds,
                    ),
                    provenance=Provenance(
                        source_system="opensearch",
                        query=f"{self.index} level:({' OR '.join(self.levels)}) service.name:{service}",
                    ),
                )
            )

        for hit in body.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            service = _first(source, _SERVICE_FIELDS)
            message = _first(source, _MESSAGE_FIELDS)

            if not service:
                # Cannot be attributed to anything, so it cannot inform an
                # incident. Held rather than dropped: unattributable logs mean a
                # shipper is misconfigured, which is worth knowing.
                harvest.quarantined.append(
                    QuarantinedEvent(
                        raw={"_id": hit.get("_id"), "_source": source},
                        source=self.name,
                        reason="log line has no recognizable service field",
                        observed_at=observed,
                    )
                )
                continue

            level = str(_first(source, _LEVEL_FIELDS) or "error").lower()
            harvest.events.append(
                Event(
                    event_class=EventClass.LOG,
                    source=self.name,
                    source_version=self.version,
                    occurred_at=_parse_time(source.get("@timestamp")) or observed,
                    observed_at=observed,
                    entity_ref=EntityRef(
                        kind=EntityKind.SERVICE, id=str(service), name=str(service)
                    ),
                    severity=_LEVEL_SEVERITY.get(level, Severity.WARNING),
                    payload=LogPayload(
                        # Verbatim. A log line is attacker-influenced text and is
                        # carried as data, never parsed into an instruction.
                        message=str(message or "")[:2000],
                        level=level,
                        fields={
                            k: str(v)
                            for k, v in source.items()
                            if k not in {"message", "@timestamp"} and not isinstance(v, (dict, list))
                        },
                        trace_id=str(source.get("trace.id") or source.get("traceId") or "") or None,
                    ),
                    provenance=Provenance(
                        source_system="opensearch",
                        query=f"{self.index}/_doc/{hit.get('_id')}",
                    ),
                )
            )

        return harvest


def _first(source: dict, fields: tuple[str, ...]):
    """First present field, supporting dotted paths as either nested objects or
    literal keys — shippers disagree about which they emit."""
    for field in fields:
        if field in source and source[field]:
            return source[field]
        cursor = source
        for part in field.split("."):
            if not isinstance(cursor, dict) or part not in cursor:
                cursor = None
                break
            cursor = cursor[part]
        if cursor:
            return cursor
    return None


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
