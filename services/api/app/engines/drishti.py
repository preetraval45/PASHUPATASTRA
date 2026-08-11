"""Drishti — perception orchestration.

Polls connectors, persists what they saw, and reconciles the topology graph.

The ordering here matters. Events are written before the graph is updated, so a
crash mid-cycle leaves telemetry that can be replayed rather than a graph that
has moved ahead of the evidence supporting it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from drishti import Connector, Harvest, OtlpReceiver, Window
from drishti.topology import TopologyBuilder
from pashupatastra import Detector, Finding

from ..db import PostgresStore
from ..graph import GraphStore
from .audit import AUDIT, AuditKind, AuditRecord
from .buffer import BufferedIngestion


@dataclass
class PollResult:
    started_at: datetime
    events_stored: int = 0
    quarantined: int = 0
    nodes_upserted: int = 0
    edges_upserted: int = 0
    dropped: int = 0
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.errors


class Drishti:
    def __init__(
        self,
        connectors: list[Connector],
        store: PostgresStore | None = None,
        graph: GraphStore | None = None,
        builder: TopologyBuilder | None = None,
        ingestion: BufferedIngestion | None = None,
        detector: Detector | None = None,
    ) -> None:
        self.connectors = connectors
        self.store = store or PostgresStore()
        self.graph = graph or GraphStore()
        self.builder = builder or TopologyBuilder()
        # Events go through a bounded buffer so a telemetry spike cannot block
        # the poll loop on database writes — the failure mode where the system
        # stalls exactly when it is busiest.
        self.ingestion = ingestion or BufferedIngestion()
        # Baselines live in the detector and are learned across polls, so it is
        # held for the lifetime of the engine rather than rebuilt per cycle —
        # a detector recreated each poll would never warm up and would report
        # silence forever, which reads as an all-clear.
        self.detector = detector or Detector()

    def receive_otlp(self, payload: dict) -> PollResult:
        """Ingest a pushed OTLP trace export.

        Same persistence and reconciliation path as `poll`, because the
        difference between push and pull ends at the connector: downstream, an
        event is an event.
        """
        result = PollResult(started_at=datetime.now().astimezone())
        harvest = OtlpReceiver().receive(payload)
        return self._absorb(harvest, result, source="otlp")

    def poll(self, window: Window | None = None) -> PollResult:
        window = window or Window.trailing(300)
        result = PollResult(started_at=datetime.now().astimezone())

        harvest = Harvest()
        for connector in self.connectors:
            try:
                harvest.extend(connector.poll(window))
            except Exception as exc:
                # One failing connector must not stop the others. Partial
                # perception is degraded, not useless — but it is recorded, so
                # nothing downstream mistakes a blind spot for an all-clear.
                harvest.errors.append(f"{connector.name}: {type(exc).__name__}: {exc}")

        return self._absorb(
            harvest,
            result,
            source=f"{len(self.connectors)} connector(s)",
            detail={
                "window_start": window.start.isoformat(),
                "window_end": window.end.isoformat(),
            },
        )

    def _absorb(
        self,
        harvest: Harvest,
        result: PollResult,
        source: str,
        detail: dict | None = None,
    ) -> PollResult:
        """Persist, then reconcile. Events are written first so a crash mid-cycle
        leaves telemetry that can be replayed, rather than a graph that has moved
        ahead of the evidence supporting it."""
        result.errors = list(harvest.errors)

        result.dropped = self.ingestion.submit(harvest.events)
        written, write_errors = self.ingestion.flush(self.store.save_events)
        result.events_stored = written
        result.errors.extend(write_errors)
        if result.dropped:
            # Never silent: "we saw nothing" and "we could not keep up" demand
            # opposite responses.
            result.errors.append(
                f"ingestion buffer dropped {result.dropped} events under load"
            )

        result.quarantined = self.store.quarantine(harvest.quarantined)

        # Detection runs on what was observed, after persistence: a finding
        # that cannot cite a stored event is not usable downstream.
        result.findings = self.detector.process(harvest.events)

        delta = self.builder.build(harvest.events, observed_edges=harvest.edges)
        result.nodes_upserted = self.graph.upsert_nodes(delta.node_list)
        result.edges_upserted = self.graph.upsert_edges(delta.edge_list)

        AUDIT.append(
            AuditRecord(
                kind=AuditKind.OBSERVATION,
                actor="drishti",
                summary=(
                    f"ingested from {source}: {result.events_stored} events, "
                    f"{result.nodes_upserted} nodes, {result.edges_upserted} edges, "
                    f"{len(result.findings)} findings"
                ),
                detail={
                    **(detail or {}),
                    "quarantined": result.quarantined,
                    "dropped": result.dropped,
                    "buffer": self.ingestion.buffer.stats.snapshot(),
                    "detector": self.detector.warmup(),
                    "findings": [f.describe() for f in result.findings],
                    "errors": result.errors,
                },
            )
        )
        return result
