"""Prometheus connector.

Reads from a Prometheus-compatible API. Amazon Managed Prometheus speaks the
same query protocol, so the only difference on AWS is the base URL and a signed
request — the normalization below is identical either way (Platform ADR).
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
from pashupatastra.events import MetricPayload

from .base import Connector, Harvest, Window

# Which label identifies the entity a series belongs to, in preference order.
# Prometheus has no single convention, so this is a ranked search rather than a
# lookup — and a series matching none of them is quarantined, not guessed at.
_ENTITY_LABELS = ("service", "job", "kubernetes_name", "container", "instance", "pod")

_KIND_BY_LABEL = {
    "service": EntityKind.SERVICE,
    "job": EntityKind.SERVICE,
    "kubernetes_name": EntityKind.SERVICE,
    "container": EntityKind.CONTAINER,
    "pod": EntityKind.POD,
    "instance": EntityKind.HOST,
}


class PrometheusConnector(Connector):
    name = "prometheus"

    def __init__(
        self,
        base_url: str = "http://localhost:9090",
        queries: dict[str, str] | None = None,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        # Named queries rather than a scrape of everything: the reasoning layer
        # needs a small set of well-understood signals, not every series in the
        # TSDB. Adding one is a deliberate act.
        self.queries = queries or {
            "cpu_usage_pct": "100 - (avg by (instance) (rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)",
            "memory_usage_pct": "100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)",
            "http_error_rate_pct": "100 * sum by (job) (rate(http_requests_total{status=~'5..'}[5m])) / sum by (job) (rate(http_requests_total[5m]))",
            "http_latency_p95_seconds": "histogram_quantile(0.95, sum by (job, le) (rate(http_request_duration_seconds_bucket[5m])))",
            "up": "up",
        }

    # --- http ---------------------------------------------------------------

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _query(self, expr: str, at: datetime) -> list[dict]:
        response = self._http().get(
            f"{self.base_url}/api/v1/query",
            params={"query": expr, "time": at.timestamp()},
        )
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "success":
            raise RuntimeError(body.get("error", "prometheus query failed"))
        return body["data"]["result"]

    # --- normalization ------------------------------------------------------

    @staticmethod
    def _entity(labels: dict[str, str]) -> EntityRef | None:
        for label in _ENTITY_LABELS:
            value = labels.get(label)
            if value:
                return EntityRef(
                    kind=_KIND_BY_LABEL.get(label, EntityKind.SERVICE),
                    id=value,
                    name=value,
                    namespace=labels.get("namespace"),
                    cluster=labels.get("cluster"),
                )
        return None

    @staticmethod
    def _severity(metric_name: str, value: float) -> Severity | None:
        """Coarse triage only.

        This is not anomaly detection — that is Buddhi's job against learned
        baselines (Phase 2). A connector that decided what counts as abnormal
        would be making a reasoning decision at the perception layer.
        """
        if metric_name == "up":
            return Severity.CRITICAL if value == 0 else Severity.INFO
        if metric_name.endswith("_pct"):
            if value >= 90:
                return Severity.CRITICAL
            if value >= 75:
                return Severity.WARNING
        return None

    def poll(self, window: Window) -> Harvest:
        harvest = Harvest()
        observed = datetime.now().astimezone()

        for metric_name, expr in self.queries.items():
            try:
                results = self._query(expr, window.end)
            except Exception as exc:
                harvest.errors.append(f"{metric_name}: {type(exc).__name__}: {exc}")
                continue

            for series in results:
                labels = series.get("metric", {})
                raw_time, raw_value = series["value"]
                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    # NaN and friends are absence of data, not a measurement of
                    # zero. Recording them as zero would invent a healthy signal.
                    continue

                entity = self._entity(labels)
                if entity is None:
                    harvest.quarantined.append(
                        QuarantinedEvent(
                            raw={"metric": labels, "value": raw_value, "query": expr},
                            source=self.name,
                            reason="no recognizable entity label",
                            observed_at=observed,
                        )
                    )
                    continue

                harvest.events.append(
                    Event(
                        event_class=EventClass.METRIC,
                        source=self.name,
                        source_version=self.version,
                        occurred_at=datetime.fromtimestamp(float(raw_time), tz=timezone.utc),
                        observed_at=observed,
                        entity_ref=entity,
                        severity=self._severity(metric_name, value),
                        payload=MetricPayload(
                            name=metric_name,
                            value=value,
                            unit="percent" if metric_name.endswith("_pct") else None,
                            window_seconds=int(
                                (window.end - window.start).total_seconds()
                            ),
                        ),
                        provenance=Provenance(
                            source_system="prometheus",
                            query=expr,
                            url=f"{self.base_url}/graph?g0.expr={expr}",
                        ),
                        labels={k: v for k, v in labels.items() if k != "__name__"},
                    )
                )

        return harvest
