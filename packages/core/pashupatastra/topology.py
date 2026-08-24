"""Topology graph and blast-radius computation.

Backing store is undecided (Postgres recursive CTEs vs. a graph store) — see
docs/adr/README.md. This in-memory implementation defines the semantics that any
store must reproduce, and is what the benchmark runs against.
"""

from __future__ import annotations

from collections import deque

from pydantic import BaseModel, Field

from .events import EntityRef


class Node(BaseModel):
    ref: EntityRef
    owner: str | None = None
    estimated_users: int = 0


class Edge(BaseModel):
    """`source` depends on `target`: a failure in target propagates to source.

    In the security domain the same direction reads as *what is at risk from
    what*: an asset an account can reach is an asset that depends on that
    account staying honest, so the edge runs from the asset to the account and
    compromise flows target to source. It reads backwards to anyone thinking
    "access goes from the account to the asset" — but blast radius walks
    dependents, and getting it the other way round would report that
    compromising a mailbox endangers the attacker.
    """

    source: str
    target: str
    kind: str = "depends_on"

    evidence: list[str] = Field(default_factory=list)
    """Event ids establishing that this path exists.

    An edge is a claim — *this account could reach that asset* — and the map is
    the thing that is supposed to be checkable, so it carries a citation like
    every other claim (rule 1 in CLAUDE.md). Empty is allowed because a
    connector observing a live dependency has its own provenance on the
    observation rather than on the edge; a *written scenario* asserting an edge
    it cannot cite is inventing structure, and `testaccesspaths.py` fails on it.
    """


class BlastRadius(BaseModel):
    origin: str
    affected: list[str] = Field(default_factory=list)
    estimated_users: int = 0

    @property
    def entity_count(self) -> int:
        return len(self.affected)


class TopologyGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._dependents: dict[str, set[str]] = {}

    def add_node(self, node: Node) -> None:
        self._nodes[node.ref.key()] = node
        self._dependents.setdefault(node.ref.key(), set())

    def add_edge(self, edge: Edge) -> None:
        # Traversal follows dependents: who breaks when `target` breaks.
        self._dependents.setdefault(edge.target, set()).add(edge.source)
        self._dependents.setdefault(edge.source, set())

    def has(self, key: str) -> bool:
        return key in self._nodes

    def blast_radius(self, origin: str, max_depth: int = 10) -> BlastRadius:
        """Everything downstream of a failure at `origin`, plus affected users."""
        seen: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(origin, 0)])
        while queue:
            key, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for dependent in self._dependents.get(key, set()):
                if dependent not in seen:
                    seen.add(dependent)
                    queue.append((dependent, depth + 1))
        users = sum(self._nodes[k].estimated_users for k in seen if k in self._nodes)
        return BlastRadius(origin=origin, affected=sorted(seen), estimated_users=users)

    def adjacent(self, a: str, b: str, max_depth: int = 3) -> bool:
        """Topology adjacency gate for correlation.

        Two services degrading in the same minute are two incidents unless they
        are connected — this is what prevents naive time-only correlation from
        fusing unrelated failures.
        """
        if a == b:
            return True
        return b in self.blast_radius(a, max_depth).affected or (
            a in self.blast_radius(b, max_depth).affected
        )
