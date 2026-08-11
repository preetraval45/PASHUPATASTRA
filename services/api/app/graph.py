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

    def stale_nodes(self, older_than: timedelta) -> list[dict]:
        """Nodes not seen recently, with how long they have been missing."""
        cutoff = datetime.now().astimezone() - older_than
        with connect(self.database_url) as conn:
            rows = conn.execute(
                """
                SELECT key, kind, name, last_seen_at,
                       EXTRACT(EPOCH FROM (now() - last_seen_at))::BIGINT AS missing_seconds
                FROM topology_node
                WHERE last_seen_at < %s
                ORDER BY last_seen_at
                """,
                (cutoff,),
            ).fetchall()
        return [
            {
                "key": r["key"],
                "kind": r["kind"],
                "name": r["name"],
                "last_seen": r["last_seen_at"].isoformat(),
                "missing_seconds": int(r["missing_seconds"]),
            }
            for r in rows
        ]

    def prune_stale(self, older_than: timedelta, dry_run: bool = True) -> dict:
        """Remove nodes not seen for `older_than`.

        **Dry-run by default, and never called automatically.** The temptation
        is to expire stale nodes on a timer, and it is the wrong instinct: a
        node disappears either because it was decommissioned or because the
        connector watching it broke, and those demand opposite responses. Worse,
        deleting on the second case shrinks blast radius — which lowers
        effective risk, which can hand an action more autonomy than it should
        have. Silence would make the system *more* willing to act precisely
        because it had gone blind.

        So expiry is an explicit, audited act with a stated threshold, and the
        default answer to "should this be removed" is "a human decides".
        """
        candidates = self.stale_nodes(older_than)
        if dry_run or not candidates:
            return {
                "dry_run": True,
                "candidates": candidates,
                "removed": 0,
                "edges_removed": 0,
            }

        keys = [c["key"] for c in candidates]
        with connect(self.database_url) as conn:
            edges = conn.execute(
                "DELETE FROM topology_edge WHERE source_key = ANY(%s) OR target_key = ANY(%s)",
                (keys, keys),
            ).rowcount
            nodes = conn.execute(
                "DELETE FROM topology_node WHERE key = ANY(%s)", (keys,)
            ).rowcount
            conn.commit()

        return {
            "dry_run": False,
            "candidates": candidates,
            "removed": nodes,
            "edges_removed": edges,
        }

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

    def snapshot(self, limit: int = 400) -> dict:
        """Nodes and edges for rendering, each node carrying its worst recent
        severity.

        Worst rather than latest: a service that emitted `critical` then `info`
        seconds later is not healthy, it is flapping, and showing the newest
        reading would hide the incident behind its own recovery.
        """
        with connect(self.database_url) as conn:
            nodes = conn.execute(
                """
                SELECT n.key, n.kind, n.name, n.namespace, n.estimated_users,
                       s.severity, s.last_seen
                FROM topology_node n
                LEFT JOIN LATERAL (
                    SELECT
                        CASE
                            WHEN bool_or(e.severity = 'critical') THEN 'critical'
                            WHEN bool_or(e.severity = 'warning')  THEN 'warning'
                            WHEN bool_or(e.severity = 'info')     THEN 'info'
                        END AS severity,
                        max(e.observed_at) AS last_seen
                    FROM event e
                    WHERE e.entity_key = n.key
                      AND e.observed_at > now() - interval '15 minutes'
                ) s ON true
                ORDER BY n.key
                LIMIT %s
                """,
                (limit,),
            ).fetchall()

            keys = [row["key"] for row in nodes]
            edges = (
                conn.execute(
                    "SELECT source_key, target_key, kind FROM topology_edge"
                    " WHERE source_key = ANY(%s) AND target_key = ANY(%s)",
                    (keys, keys),
                ).fetchall()
                if keys
                else []
            )

        return {
            "nodes": [
                {
                    "key": row["key"],
                    "kind": row["kind"],
                    "name": row["name"],
                    "namespace": row["namespace"],
                    "estimated_users": row["estimated_users"],
                    "severity": row["severity"],
                    "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                }
                for row in nodes
            ],
            "edges": [
                {"source": e["source_key"], "target": e["target_key"], "kind": e["kind"]}
                for e in edges
            ],
        }

    def counts(self) -> tuple[int, int]:
        with connect(self.database_url) as conn:
            nodes = conn.execute("SELECT count(*) AS n FROM topology_node").fetchone()["n"]
            edges = conn.execute("SELECT count(*) AS n FROM topology_edge").fetchone()["n"]
        return int(nodes), int(edges)
