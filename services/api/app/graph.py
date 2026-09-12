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
from pashupatastra.events import Event

from .db import connect
from .graphmemory import MemoryGraph

MIRROR = MemoryGraph()
"""Process-wide, so every `GraphStore()` sees the same graph when there is no
database. Per-instance state would give each request an empty map."""

_resolved: bool | None = None


def _durable(database_url: str | None = None) -> bool:
    """Whether anything durable is backing the graph — see `backend.py`, which
    makes this decision once for every store rather than three times."""
    from .backend import durable

    return durable() is not None


def entitystore(database_url: str | None = None):
    """Whatever is currently holding events and entity rows.

    `MemoryGraph` implements the same `save_events` / `entity` / `entity_events`
    surface as `PostgresStore`, so callers do not need to know which answered —
    only that reaching for `PostgresStore` directly would make an entity view
    fail outright on a deployment that has no database.
    """
    from .backend import durable

    return durable() or MIRROR


class GraphStore:
    """Postgres-backed when a database is reachable, in-memory otherwise.

    The fallback exists for the same reason `Store`'s does: an empty graph
    reports a blast radius of zero, and a blast radius of zero silently lowers
    risk. A deployment without Postgres should show a map and report `degraded`,
    not answer every topology question with nothing.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    @property
    def durable(self) -> bool:
        return _durable(self.database_url)

    @property
    def _delegate(self):
        """Whoever answers graph questions, or `None` for the Postgres path.

        `MemoryGraph` and `DynamoStore` both implement the graph surface and say
        so with `answers_graph`. Postgres does not: its topology lives in the
        SQL further down this file, where it has always been. Asking
        `_durable()` alone was enough while Postgres was the only durable store
        and became wrong the moment a second one existed — DynamoDB would have
        been routed into `connect()` and tried to open a Postgres connection.
        """
        from .backend import durable

        store = durable()
        if store is None:
            return MIRROR
        return store if getattr(store, "answers_graph", False) else None

    # --- reconciliation -----------------------------------------------------

    def upsert_nodes(self, nodes: list[Node]) -> int:
        if (mirror := self._delegate) is not None:
            return mirror.upsert_nodes(nodes)

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
        if (mirror := self._delegate) is not None:
            return mirror.upsert_edges(edges)

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
        if (mirror := self._delegate) is not None:
            return mirror.blast_radius(origin, max_depth=max_depth)

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
        if (mirror := self._delegate) is not None:
            return mirror.adjacent(a, b, max_depth=max_depth)

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
        if (mirror := self._delegate) is not None:
            return mirror.snapshot(limit=limit)

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
        if (mirror := self._delegate) is not None:
            return mirror.counts()

        with connect(self.database_url) as conn:
            nodes = conn.execute("SELECT count(*) AS n FROM topology_node").fetchone()["n"]
            edges = conn.execute("SELECT count(*) AS n FROM topology_edge").fetchone()["n"]
        return int(nodes), int(edges)


def events_by_id(store, event_ids) -> list[Event]:
    """Stored rows rebuilt into `Event`, for engines that read the typed model.

    The row shape and the domain model differ in one place: a row carries
    `entity_key` — `host:ws-0148` — where `Event` carries a nested `EntityRef`.
    Splitting on the first colon is correct rather than convenient, because
    `EntityRef.key()` is `f"{kind}:{id}"` and a network-flow id contains further
    colons of its own (`ws-0148->198.51.100.74:8443`); splitting on the last
    would silently produce a different entity.

    Ids that resolve to nothing are skipped rather than faked. A caller drafting
    from these has to be able to tell that a record was missing, and an `Event`
    invented to stand in for one would be indistinguishable from a real read.
    """
    from pashupatastra.events import EntityKind, EntityRef

    if store is None:
        return []

    rebuilt: list[Event] = []
    for event_id in event_ids:
        row = store.event(event_id)
        if row is None:
            continue
        key = str(row.get("entity_key") or "")
        kind, _, identifier = key.partition(":")
        if not identifier:
            continue
        try:
            ref = EntityRef(kind=EntityKind(kind), id=identifier, name=identifier)
            rebuilt.append(
                Event.model_validate(
                    {
                        **{k: v for k, v in row.items() if k != "entity_key"},
                        "entity_ref": ref.model_dump(),
                    }
                )
            )
        except (ValueError, KeyError):
            # A row we cannot rebuild is dropped for the same reason it is not
            # faked. The caller sees fewer events than it cited, which is the
            # honest signal; a partially-invented one is not.
            continue
    return rebuilt


def chain_times(store, incident) -> dict[str, datetime]:
    """When each event the causal chain cites was observed.

    One implementation, shared by the route and the chat tool. Two would be two
    answers to "when did this step happen", and the counterfactual's entire
    output is a comparison against those moments — so a drift between them would
    show up as the page and the agent disagreeing about how much acting earlier
    would have saved, which is the one number this feature exists to produce.

    An id that resolves to nothing is simply absent. The counterfactual then
    reports that step as untimed rather than placing it, because a step assumed
    early inflates the estimate and one assumed late deflates it.
    """
    if store is None:
        return {}

    times: dict[str, datetime] = {}
    for link in incident.causal_chain:
        for ref in link.evidence:
            if ref in times:
                continue
            row = store.event(ref)
            if row is None:
                continue
            raw = row.get("occurred_at")
            if isinstance(raw, datetime):
                times[ref] = raw
            elif isinstance(raw, str):
                times[ref] = datetime.fromisoformat(raw)
    return times
