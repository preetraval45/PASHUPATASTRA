"""Topology construction from connector output.

Nodes are cheap: anything that emits an event exists, so every event contributes
one. Edges are expensive, and this module is deliberately strict about them.

A dependency edge is a claim that one thing breaking will break another. Get it
wrong and blast radius is wrong, and blast radius feeds risk scoring — so a
fabricated edge inflates the authority the system grants itself, and a missing
edge hides real impact. Edges therefore come only from signals that actually
observe a call happening:

    traces          A called B — direct evidence, the strongest source
    k8s ownership   pod belongs to deployment — structural, not inferred
    config          declared dependencies — explicit, human-authored

Co-occurrence, shared labels, name similarity, and correlated timing are **not**
edge sources. Two services degrading together is what correlation is for; using
it to create topology would let the graph confirm its own guesses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pashupatastra import EntityKind, EntityRef, Event, EventClass, Node
from pashupatastra.events import TracePayload
from pashupatastra.topology import Edge

# Kinds that can meaningfully depend on something else. A host does not "depend
# on" a database in the sense blast radius means, so edges are not drawn to it.
_DEPENDABLE = {
    EntityKind.SERVICE,
    EntityKind.DATABASE,
    EntityKind.CACHE,
    EntityKind.QUEUE,
    EntityKind.ENDPOINT,
    EntityKind.LOADBALANCER,
    EntityKind.CLOUD_RESOURCE,
}


@dataclass
class TopologyDelta:
    """What one batch of events says the graph should contain."""

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: set[tuple[str, str, str]] = field(default_factory=set)

    @property
    def edge_list(self) -> list[Edge]:
        return [Edge(source=s, target=t, kind=k) for s, t, k in sorted(self.edges)]

    @property
    def node_list(self) -> list[Node]:
        return [self.nodes[key] for key in sorted(self.nodes)]

    def merge(self, other: "TopologyDelta") -> "TopologyDelta":
        for key, node in other.nodes.items():
            existing = self.nodes.get(key)
            if existing is None:
                self.nodes[key] = node
            else:
                # Keep the richer reading: a connector that cannot see user
                # counts must not erase what another established.
                existing.estimated_users = max(
                    existing.estimated_users, node.estimated_users
                )
                existing.owner = existing.owner or node.owner
        self.edges |= other.edges
        return self


class TopologyBuilder:
    """Derives nodes and edges from normalized events."""

    def build(self, events: list[Event]) -> TopologyDelta:
        delta = TopologyDelta()
        for event in events:
            self._add_node(delta, event.entity_ref)
            if event.event_class is EventClass.TRACE:
                self._add_trace_edges(delta, event)
        return delta

    @staticmethod
    def _add_node(delta: TopologyDelta, ref: EntityRef) -> Node:
        key = ref.key()
        node = delta.nodes.get(key)
        if node is None:
            node = Node(ref=ref)
            delta.nodes[key] = node
        return node

    def _add_trace_edges(self, delta: TopologyDelta, event: Event) -> None:
        """A trace records the actual call path, so consecutive hops are a real
        dependency: the caller breaks when the callee does."""
        payload = event.payload
        if not isinstance(payload, TracePayload):
            return

        hops = [hop for hop in payload.service_hops if hop]
        for caller, callee in zip(hops, hops[1:]):
            if caller == callee:
                continue  # self-call; not a dependency
            source = EntityRef(kind=EntityKind.SERVICE, id=caller, name=caller)
            target = EntityRef(kind=EntityKind.SERVICE, id=callee, name=callee)
            self._add_node(delta, source)
            self._add_node(delta, target)
            delta.edges.add((source.key(), target.key(), "depends_on"))

    @staticmethod
    def declared(dependencies: dict[str, list[str]]) -> TopologyDelta:
        """Edges from an explicit, human-authored dependency map.

        The escape hatch for things no telemetry reveals — a cron job's database,
        a third-party API. Explicit beats inferred, so these are trusted, but
        they are also the only place a human can be wrong without the system
        being able to tell.
        """
        delta = TopologyDelta()
        for source, targets in dependencies.items():
            source_ref = _parse_key(source)
            TopologyBuilder._add_node(delta, source_ref)
            for target in targets:
                target_ref = _parse_key(target)
                TopologyBuilder._add_node(delta, target_ref)
                if target_ref.kind in _DEPENDABLE:
                    delta.edges.add((source_ref.key(), target_ref.key(), "depends_on"))
        return delta


def _parse_key(key: str) -> EntityRef:
    """`"service:checkout"` → EntityRef. Bare names default to a service."""
    if ":" in key:
        kind, _, name = key.partition(":")
        return EntityRef(kind=EntityKind(kind), id=name, name=name)
    return EntityRef(kind=EntityKind.SERVICE, id=key, name=key)
