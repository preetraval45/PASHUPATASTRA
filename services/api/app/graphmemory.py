"""In-memory topology mirror, for deployments with no Postgres.

Mirrors the read surface of `GraphStore` so the dashboard renders a service map
without a database — the same arrangement `Store` already has for incidents.

Traversal is **not** reimplemented here. `TopologyGraph` in packages/core is the
reference implementation of blast radius and adjacency, and `testgraph.py`
already asserts the Postgres store agrees with it; a third copy of that walk
would be a third answer to a question risk scoring depends on. What this module
adds is the projection Postgres does in SQL and core has no opinion about:
severity rollup, the node/edge snapshot, and per-entity event history.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pashupatastra import BlastRadius, Edge, Node
from pashupatastra.events import Severity

SEVERITY_WINDOW = timedelta(minutes=15)
"""Matches the interval in `GraphStore.snapshot`. Both stores must answer the
same question or the map changes meaning when a database appears."""

_RANK = {Severity.CRITICAL: 3, Severity.WARNING: 2, Severity.INFO: 1}


class MemoryGraph:
    def __init__(self) -> None:
        from pashupatastra.topology import TopologyGraph

        self._graph = TopologyGraph()
        self._nodes: dict[str, Node] = {}
        self._edges: dict[tuple[str, str, str], Edge] = {}
        self._events: dict[str, list[dict]] = {}
        self._first_seen: dict[str, datetime] = {}
        self._last_seen: dict[str, datetime] = {}

    # --- reconciliation -----------------------------------------------------

    def upsert_nodes(self, nodes: list[Node]) -> int:
        now = datetime.now().astimezone()
        for node in nodes:
            key = node.ref.key()
            existing = self._nodes.get(key)
            if existing is not None and node.estimated_users == 0:
                # A connector that cannot see user counts must not zero out what
                # another connector established — the same rule the upsert SQL
                # enforces with its CASE expression.
                node = node.model_copy(update={"estimated_users": existing.estimated_users})
            self._nodes[key] = node
            self._graph.add_node(node)
            self._first_seen.setdefault(key, now)
            self._last_seen[key] = now
        return len(nodes)

    def upsert_edges(self, edges: list[Edge]) -> int:
        for edge in edges:
            self._edges[(edge.source, edge.target, edge.kind)] = edge
            self._graph.add_edge(edge)
        return len(edges)

    def save_events(self, events: list) -> int:
        for event in events:
            key = event.entity_ref.key()
            self._events.setdefault(key, []).append(
                {
                    "id": event.id,
                    "event_class": str(event.event_class),
                    "source": event.source,
                    "occurred_at": event.occurred_at,
                    "observed_at": event.observed_at,
                    "severity": str(event.severity) if event.severity else None,
                    "payload": event.payload.model_dump(mode="json"),
                    "provenance": event.provenance.model_dump(mode="json"),
                    "labels": dict(event.labels),
                }
            )
            seen = self._last_seen.get(key)
            if seen is None or event.observed_at > seen:
                self._last_seen[key] = event.observed_at
            first = self._first_seen.get(key)
            if first is None or event.observed_at < first:
                self._first_seen[key] = event.observed_at
        return len(events)

    def quarantine(self, events: list) -> int:
        """Malformed events are counted, not kept.

        The Postgres store keeps the payloads for inspection. Holding them in a
        process that restarts would give a quarantine that looks empty because
        it was cleared, not because nothing failed — so this reports the count
        and says so, rather than implying a queue it does not have.
        """
        return len(events)

    def count_events(self) -> int:
        return sum(len(events) for events in self._events.values())

    # --- reads --------------------------------------------------------------

    def blast_radius(self, origin: str, max_depth: int = 10) -> BlastRadius:
        return self._graph.blast_radius(origin, max_depth=max_depth)

    def adjacent(self, a: str, b: str, max_depth: int = 3) -> bool:
        return self._graph.adjacent(a, b, max_depth=max_depth)

    def counts(self) -> tuple[int, int]:
        return len(self._nodes), len(self._edges)

    def severity(self, key: str, now: datetime | None = None) -> str | None:
        """Worst severity in the window, not the latest.

        A service that emitted `critical` and then `info` seconds later is
        flapping, not healthy, and the newest reading would hide the incident
        behind its own recovery.
        """
        cutoff = (now or datetime.now().astimezone()) - SEVERITY_WINDOW
        worst = 0
        for event in self._events.get(key, ()):
            if event["observed_at"] <= cutoff or event["severity"] is None:
                continue
            worst = max(worst, _RANK.get(Severity(event["severity"]), 0))
        return next((s.value for s, r in _RANK.items() if r == worst), None)

    def snapshot(self, limit: int = 400) -> dict:
        keys = sorted(self._nodes)[:limit]
        included = set(keys)
        return {
            "nodes": [
                {
                    "key": key,
                    "kind": str(self._nodes[key].ref.kind),
                    "name": self._nodes[key].ref.name,
                    "namespace": self._nodes[key].ref.namespace,
                    "estimated_users": self._nodes[key].estimated_users,
                    "severity": self.severity(key),
                    "last_seen": last.isoformat() if (last := self._last_seen.get(key)) else None,
                }
                for key in keys
            ],
            "edges": [
                {"source": e.source, "target": e.target, "kind": e.kind}
                for e in self._edges.values()
                if e.source in included and e.target in included
            ],
        }

    def entity(self, entity_key: str) -> dict | None:
        node = self._nodes.get(entity_key)
        if node is None:
            return None
        first = self._first_seen.get(entity_key)
        last = self._last_seen.get(entity_key)
        return {
            "key": entity_key,
            "kind": str(node.ref.kind),
            "name": node.ref.name,
            "namespace": node.ref.namespace,
            "cluster": node.ref.cluster,
            "owner": node.owner,
            "estimated_users": node.estimated_users,
            "first_seen": first.isoformat() if first else None,
            "last_seen": last.isoformat() if last else None,
        }

    def entity_events(self, entity_key: str, limit: int = 50) -> list[dict]:
        events = sorted(
            self._events.get(entity_key, ()),
            key=lambda e: (e["occurred_at"], e["id"]),
            reverse=True,
        )[:limit]
        return [
            {**e, "occurred_at": e["occurred_at"].isoformat(), "observed_at": e["observed_at"].isoformat()}
            for e in events
        ]
