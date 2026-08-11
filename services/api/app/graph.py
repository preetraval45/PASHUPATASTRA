"""Postgres-backed topology graph.

`TopologyGraph` in packages/core is the reference implementation: it defines the
semantics any store must reproduce. This is the Postgres default from the Graph
ADR, and `testgraph.py` asserts the two agree on every case rather than trusting
that they do.

Reconciliation is upsert-and-decay, not delete-and-rebuild: a connector that
fails one poll must not empty the graph, because an empty graph reports a blast
radius of zero, and a blast radius of zero silently lowers risk.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pashupatastra import BlastRadius, Edge, Node

from .db import connect


class GraphStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # --- reconciliation -----------------------------------------------------

    def upsert_nodes(self, nodes: list[Node]) -> int:
        if not nodes:
            return 0
        with connect(self.database_url) as conn:
            for node in nodes:
                conn.execute(
                    """
                    INSERT INTO topology_node
                        (key, kind, entity_id, name, cluster, namespace, owner, estimated_users)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET
                        name = EXCLUDED.name,
                        cluster = EXCLUDED.cluster,
                        namespace = EXCLUDED.namespace,
                        owner = COALESCE(EXCLUDED.owner, topology_node.owner),
                        -- Only overwrite the user estimate when the new reading
                        -- has one; a connector that cannot see user counts must
                        -- not zero out what another connector established.
                        estimated_users = CASE
                            WHEN EXCLUDED.estimated_users > 0 THEN EXCLUDED.estimated_users
                            ELSE topology_node.estimated_users
                        END,
                        last_seen_at = now()
                    """,
                    (
                        node.ref.key(),
                        node.ref.kind.value,
                        node.ref.id,
                        node.ref.name,
                        node.ref.cluster,
                        node.ref.namespace,
                        node.owner,
                        node.estimated_users,
                    ),
                )
            conn.commit()
        return len(nodes)

    def upsert_edges(self, edges: list[Edge]) -> int:
        if not edges:
            return 0
        with connect(self.database_url) as conn:
            for edge in edges:
                # Both endpoints must already exist; a dangling edge would make
                # blast radius traverse into a node nothing knows about.
                conn.execute(
                    """
                    INSERT INTO topology_edge (source_key, target_key, kind)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (source_key, target_key, kind) DO NOTHING
                    """,
                    (edge.source, edge.target, edge.kind),
                )
            conn.commit()
        return len(edges)

    def stale_nodes(self, older_than: timedelta) -> list[str]:
        """Nodes not seen recently.

        Surfaced rather than auto-deleted. A node disappearing may mean it was
        decommissioned, or may mean the connector broke — and those need
        different responses, so a human or a later reconciliation policy decides.
        """
        cutoff = datetime.now().astimezone() - older_than
        with connect(self.database_url) as conn:
            rows = conn.execute(
                "SELECT key FROM topology_node WHERE last_seen_at < %s ORDER BY key", (cutoff,)
            ).fetchall()
        return [row["key"] for row in rows]

    # --- queries ------------------------------------------------------------

    def blast_radius(self, origin: str, max_depth: int = 10) -> BlastRadius:
        with connect(self.database_url) as conn:
            affected = [
                row["affected_key"]
                for row in conn.execute(
                    "SELECT affected_key FROM blast_radius(%s, %s)", (origin, max_depth)
                ).fetchall()
            ]
            users = conn.execute(
                "SELECT blast_radius_users(%s, %s) AS n", (origin, max_depth)
            ).fetchone()["n"]
        return BlastRadius(origin=origin, affected=affected, estimated_users=int(users))

    def adjacent(self, a: str, b: str, max_depth: int = 3) -> bool:
        """Correlation gate: are these two entities connected at all?"""
        if a == b:
            return True
        return b in self.blast_radius(a, max_depth).affected or (
            a in self.blast_radius(b, max_depth).affected
        )

    def counts(self) -> tuple[int, int]:
        with connect(self.database_url) as conn:
            nodes = conn.execute("SELECT count(*) AS n FROM topology_node").fetchone()["n"]
            edges = conn.execute("SELECT count(*) AS n FROM topology_edge").fetchone()["n"]
        return int(nodes), int(edges)
