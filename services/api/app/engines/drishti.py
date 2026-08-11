"""Drishti — perception orchestration.

Polls connectors, persists what they saw, and reconciles the topology graph.

The ordering here matters. Events are written before the graph is updated, so a
crash mid-cycle leaves telemetry that can be replayed rather than a graph that
has moved ahead of the evidence supporting it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from drishti import Connector, Harvest, Window
from drishti.topology import TopologyBuilder

from ..db import PostgresStore
from ..graph import GraphStore
from .audit import AUDIT, AuditKind, AuditRecord


@dataclass
class PollResult:
    started_at: datetime
    events_stored: int = 0
    quarantined: int = 0
    nodes_upserted: int = 0
    edges_upserted: int = 0
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
    ) -> None:
        self.connectors = connectors
        self.store = store or PostgresStore()
        self.graph = graph or GraphStore()
        self.builder = builder or TopologyBuilder()

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

        result.errors = list(harvest.errors)
        result.events_stored = self.store.save_events(harvest.events)
        result.quarantined = self.store.quarantine(harvest.quarantined)

        delta = self.builder.build(harvest.events, observed_edges=harvest.edges)
        result.nodes_upserted = self.graph.upsert_nodes(delta.node_list)
        result.edges_upserted = self.graph.upsert_edges(delta.edge_list)

        AUDIT.append(
            AuditRecord(
                kind=AuditKind.OBSERVATION,
                actor="drishti",
                summary=(
                    f"polled {len(self.connectors)} connector(s): "
                    f"{result.events_stored} events, {result.nodes_upserted} nodes, "
                    f"{result.edges_upserted} edges"
                ),
                detail={
                    "window_start": window.start.isoformat(),
                    "window_end": window.end.isoformat(),
                    "quarantined": result.quarantined,
                    "errors": result.errors,
                },
            )
        )
        return result
