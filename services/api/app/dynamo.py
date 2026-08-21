"""DynamoDB persistence.

The third implementation of the same seam, after Postgres and memory, and it
exists for one reason: **DynamoDB's free allowance does not expire.** RDS is the
better database for this shape of data and its free tier dies after twelve
months, at which point a demo either starts costing money or starts lying about
being durable. See docs/REBUILD.md.

The table layout is in `scripts/createdynamo.py`. Everything here is a lookup by
id or a listing of one type in time order, which is why one table and one index
covers it.

Two things worth reading before changing anything.

**The graph is read whole, every time.** `snapshot`, `counts` and `blast_radius`
each pull every node and edge rather than walking the graph inside the database.
That is deliberate: the traversal lives in `TopologyGraph` in packages/core,
which `testgraph.py` holds the Postgres store to, and a fourth implementation of
blast radius — in a query language that cannot express recursion without
contortions — would be a fourth answer to a question risk scoring depends on.
The graph is small enough that reading it costs less than getting it wrong.

**Numbers come back as `Decimal`.** DynamoDB has no float type, so anything that
crosses this boundary is converted on the way out. A `Decimal` that reaches
Pydantic validates fine and then serialises to JSON as a string, and the
dashboard renders `"0.94"` where it expected `0.94`.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from pashupatastra import BlastRadius, Edge, Incident, Node

from .config import get_settings
from .engines.audit import AuditKind, AuditRecord

SEED_VERSION = "1"
"""Bumped when the seeded scenarios change shape. The marker item carries it, so
a deployment with an older seed re-seeds instead of serving a mixture."""


def _plain(value: Any) -> Any:
    """DynamoDB's numbers to Python's.

    `Decimal` survives Pydantic validation and then serialises as a JSON string,
    so a confidence of 0.94 reaches the dashboard as "0.94" and renders as text
    where a number was expected. Converted here, once, at the boundary.
    """
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _numbers_to_decimal(value: Any) -> Any:
    """The same boundary, in the other direction. DynamoDB rejects floats."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_numbers_to_decimal(v) for v in value]
    if isinstance(value, dict):
        return {k: _numbers_to_decimal(v) for k, v in value.items()}
    return value


class DynamoStore:
    """Durable store. Mirrors the surface `PostgresStore` and `MemoryGraph` offer."""

    name = "dynamodb"

    answers_graph = True
    """Unlike `PostgresStore`, this answers topology questions itself rather
    than leaving them to SQL inside `GraphStore` — see `GraphStore._delegate`."""

    def __init__(
        self,
        table_name: str | None = None,
        region: str | None = None,
        namespace: str | None = None,
    ) -> None:
        settings = get_settings()
        self.table_name = table_name or settings.dynamo_table
        self.region = region or settings.aws_region
        self.namespace = namespace or settings.dynamo_namespace
        self._table = None
        self._sequence = 0

    def _pk(self, partition: str) -> str:
        """Partition key, namespaced.

        Every environment sharing one table is a deliberate choice: DynamoDB's
        always-free allowance is 25 capacity units *per account*, so a second
        table would halve production's headroom rather than add any.

        The namespace is what keeps that from being reckless. Without it a local
        run writes into the deployed console's data, and durability turns that
        from a mistake the next restart erases into one that stays. It already
        happened here — a test fixture reached the live service map, and an
        infrastructure incident was seeded into the security console.
        """
        return f"{self.namespace}#{partition}"

    @property
    def table(self):
        # Imported and connected lazily: a deployment with no table configured
        # should not pay for boto3's import, and `packages/core` must keep
        # running on a laptop with no cloud at all.
        if self._table is None:
            import boto3

            self._table = boto3.resource("dynamodb", region_name=self.region).Table(
                self.table_name
            )
        return self._table

    def available(self) -> bool:
        """Whether the table is there and readable."""
        try:
            self.table.load()
            return True
        except Exception:
            return False

    # --- audit ---------------------------------------------------------------

    def append_audit(self, record: AuditRecord) -> AuditRecord:
        # The sequence disambiguates records written inside the same
        # millisecond. Without it the second one overwrites the first, and an
        # audit trail that drops a record under load is not an audit trail.
        self._sequence += 1
        self.table.put_item(
            Item={
                "PK": self._pk("AUDIT"),
                "SK": f"{record.at.isoformat()}#{self._sequence:06d}",
                "at": record.at.isoformat(),
                "kind": record.kind.value,
                "actor": record.actor,
                "incident_ref": record.incident_ref or "",
                "summary": record.summary,
                "detail": json.dumps(record.detail, default=str),
            }
        )
        return record

    def audit_records(
        self, incident_ref: str | None = None, limit: int = 100
    ) -> list[AuditRecord]:
        from boto3.dynamodb.conditions import Attr, Key

        query: dict[str, Any] = {
            "KeyConditionExpression": Key("PK").eq(self._pk("AUDIT")),
            "ScanIndexForward": False,  # newest first
            "Limit": limit,
        }
        if incident_ref is not None:
            query["FilterExpression"] = Attr("incident_ref").eq(incident_ref)
            # A filter runs after the read, so the page has to be large enough
            # to still hold `limit` matches once the others are discarded.
            query["Limit"] = max(limit * 10, 100)

        rows = self.table.query(**query).get("Items", [])[:limit]
        return [
            AuditRecord(
                at=datetime.fromisoformat(row["at"]),
                kind=AuditKind(row["kind"]),
                actor=row["actor"],
                incident_ref=row.get("incident_ref") or None,
                summary=row["summary"],
                detail=json.loads(row.get("detail") or "{}"),
            )
            for row in rows
        ]

    def count_audit(self) -> int:
        from boto3.dynamodb.conditions import Key

        return int(
            self.table.query(
                KeyConditionExpression=Key("PK").eq(self._pk("AUDIT")), Select="COUNT"
            )["Count"]
        )

    # --- events --------------------------------------------------------------

    def save_events(self, events: list) -> int:
        if not events:
            return 0
        with self.table.batch_writer(overwrite_by_pkeys=["PK", "SK"]) as batch:
            for event in events:
                key = event.entity_ref.key()
                batch.put_item(
                    Item={
                        "PK": self._pk("EVENT"),
                        "SK": event.id,
                        # The index that answers "what has this entity been
                        # saying", which the table's own keys cannot.
                        "GSI1PK": f"{self.namespace}#ENTITY#{key}",
                        "GSI1SK": f"{event.occurred_at.isoformat()}#{event.id}",
                        "id": event.id,
                        "entity_key": key,
                        "event_class": str(event.event_class),
                        "source": event.source,
                        "occurred_at": event.occurred_at.isoformat(),
                        "observed_at": event.observed_at.isoformat(),
                        "severity": str(event.severity) if event.severity else "",
                        "payload": json.dumps(event.payload.model_dump(mode="json")),
                        "provenance": json.dumps(event.provenance.model_dump(mode="json")),
                        "labels": json.dumps(dict(event.labels)),
                    }
                )
        return len(events)

    def quarantine(self, events: list) -> int:
        """Counted, not kept.

        The Postgres store holds the payloads for inspection. Doing that here
        would mean a second item type and a second access pattern for something
        this deployment has never produced — the count is honest and the
        capability is not claimed.
        """
        return len(events)

    def _event_row(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "event_class": row["event_class"],
            "source": row["source"],
            "occurred_at": row["occurred_at"],
            "observed_at": row["observed_at"],
            "severity": row.get("severity") or None,
            "payload": _plain(json.loads(row.get("payload") or "{}")),
            "provenance": _plain(json.loads(row.get("provenance") or "{}")),
            "labels": _plain(json.loads(row.get("labels") or "{}")),
            "entity_key": row.get("entity_key"),
        }

    def event(self, event_id: str) -> dict | None:
        row = self.table.get_item(Key={"PK": self._pk("EVENT"), "SK": event_id}).get("Item")
        return self._event_row(row) if row else None

    def entity_events(self, entity_key: str, limit: int = 50) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        rows = self.table.query(
            IndexName="ByEntity",
            KeyConditionExpression=Key("GSI1PK").eq(f"{self.namespace}#ENTITY#{entity_key}"),
            ScanIndexForward=False,
            Limit=limit,
        ).get("Items", [])
        return [self._event_row(row) for row in rows]

    def count_events(self) -> int:
        from boto3.dynamodb.conditions import Key

        return int(
            self.table.query(
                KeyConditionExpression=Key("PK").eq(self._pk("EVENT")), Select="COUNT"
            )["Count"]
        )

    # --- topology ------------------------------------------------------------

    def upsert_nodes(self, nodes: list[Node]) -> int:
        if not nodes:
            return 0
        now = datetime.now().astimezone().isoformat()
        existing = {row["SK"]: row for row in self._all("NODE")}
        with self.table.batch_writer(overwrite_by_pkeys=["PK", "SK"]) as batch:
            for node in nodes:
                key = node.ref.key()
                was = existing.get(key)
                # A connector that cannot see user counts must not zero out what
                # another connector established — the rule the Postgres upsert
                # enforces with its CASE expression.
                users = node.estimated_users or int(_plain(was.get("estimated_users", 0)) if was else 0)
                batch.put_item(
                    Item={
                        "PK": self._pk("NODE"),
                        "SK": key,
                        "key": key,
                        "kind": str(node.ref.kind),
                        "name": node.ref.name,
                        "namespace": node.ref.namespace or "",
                        "cluster": node.ref.cluster or "",
                        "owner": node.owner or "",
                        "estimated_users": users,
                        "first_seen": (was or {}).get("first_seen", now),
                        "last_seen": now,
                    }
                )
        return len(nodes)

    def upsert_edges(self, edges: list[Edge]) -> int:
        if not edges:
            return 0
        with self.table.batch_writer(overwrite_by_pkeys=["PK", "SK"]) as batch:
            for edge in edges:
                batch.put_item(
                    Item={
                        "PK": self._pk("EDGE"),
                        "SK": f"{edge.source}|{edge.target}|{edge.kind}",
                        "source": edge.source,
                        "target": edge.target,
                        "kind": edge.kind,
                    }
                )
        return len(edges)

    def _all(self, partition: str) -> list[dict]:
        """Every item of one type. Paginated, because a `Query` returns at most
        1MB and silently stopping at the first page is how a graph quietly loses
        half its edges."""
        from boto3.dynamodb.conditions import Key

        items: list[dict] = []
        start = None
        while True:
            query: dict[str, Any] = {"KeyConditionExpression": Key("PK").eq(self._pk(partition))}
            if start:
                query["ExclusiveStartKey"] = start
            page = self.table.query(**query)
            items.extend(page.get("Items", []))
            start = page.get("LastEvaluatedKey")
            if not start:
                return items

    def entity(self, entity_key: str) -> dict | None:
        row = self.table.get_item(Key={"PK": self._pk("NODE"), "SK": entity_key}).get("Item")
        if not row:
            return None
        return {
            "key": row["key"],
            "kind": row["kind"],
            "name": row["name"],
            "namespace": row.get("namespace") or None,
            "cluster": row.get("cluster") or None,
            "owner": row.get("owner") or None,
            "estimated_users": int(_plain(row.get("estimated_users", 0))),
            "first_seen": row.get("first_seen"),
            "last_seen": row.get("last_seen"),
        }

    def counts(self) -> tuple[int, int]:
        return len(self._all("NODE")), len(self._all("EDGE"))

    def _graph(self):
        """The topology, in the reference implementation.

        Rebuilt per call rather than cached. A cache would be per-container, and
        on Lambda that means one container answering from a graph another
        container has already changed — a blast radius computed from a stale
        graph is smaller than the truth, and a smaller blast radius lowers
        effective risk.
        """
        from pashupatastra.topology import TopologyGraph
        from pashupatastra.events import EntityKind, EntityRef

        graph = TopologyGraph()
        for row in self._all("NODE"):
            kind, _, entity_id = str(row["key"]).partition(":")
            graph.add_node(
                Node(
                    ref=EntityRef(kind=EntityKind(kind), id=entity_id, name=row["name"]),
                    owner=row.get("owner") or None,
                    estimated_users=int(_plain(row.get("estimated_users", 0))),
                )
            )
        for row in self._all("EDGE"):
            graph.add_edge(Edge(source=row["source"], target=row["target"], kind=row["kind"]))
        return graph

    def blast_radius(self, origin: str, max_depth: int = 10) -> BlastRadius:
        return self._graph().blast_radius(origin, max_depth=max_depth)

    def adjacent(self, a: str, b: str, max_depth: int = 3) -> bool:
        return self._graph().adjacent(a, b, max_depth=max_depth)

    def snapshot(self, limit: int = 400, now: datetime | None = None) -> dict:
        from .graphmemory import SEVERITY_WINDOW

        cutoff = (now or datetime.now().astimezone()) - SEVERITY_WINDOW
        rank = {"critical": 3, "warning": 2, "info": 1}

        worst: dict[str, str] = {}
        latest: dict[str, str] = {}
        for row in self._all("EVENT"):
            key = row.get("entity_key")
            if not key:
                continue
            observed = row.get("observed_at")
            if observed and (not latest.get(key) or observed > latest[key]):
                latest[key] = observed
            severity = row.get("severity")
            # Worst in the window, not latest: an entity that went critical then
            # reported info seconds later is flapping, not healthy.
            if severity and observed and datetime.fromisoformat(observed) > cutoff:
                if rank.get(severity, 0) > rank.get(worst.get(key, ""), 0):
                    worst[key] = severity

        nodes = sorted(self._all("NODE"), key=lambda r: r["SK"])[:limit]
        included = {row["key"] for row in nodes}
        return {
            "nodes": [
                {
                    "key": row["key"],
                    "kind": row["kind"],
                    "name": row["name"],
                    "namespace": row.get("namespace") or None,
                    "estimated_users": int(_plain(row.get("estimated_users", 0))),
                    "severity": worst.get(row["key"]),
                    "last_seen": latest.get(row["key"]) or row.get("last_seen"),
                }
                for row in nodes
            ],
            "edges": [
                {"source": e["source"], "target": e["target"], "kind": e["kind"]}
                for e in self._all("EDGE")
                if e["source"] in included and e["target"] in included
            ],
        }

    # --- incidents -----------------------------------------------------------

    def save_incident(self, incident: Incident) -> None:
        self.table.put_item(
            Item={
                "PK": self._pk("INCIDENT"),
                "SK": incident.id,
                "opened_at": incident.opened_at.isoformat(),
                # Stored as one JSON document rather than shredded across items.
                # An incident is read and written whole, its transitions are
                # append-only, and splitting it would buy nothing but the chance
                # of loading half of one.
                "document": incident.model_dump_json(),
            }
        )

    def get_incident(self, incident_id: str) -> Incident | None:
        row = self.table.get_item(Key={"PK": self._pk("INCIDENT"), "SK": incident_id}).get("Item")
        return Incident.model_validate_json(row["document"]) if row else None

    def list_incidents(self) -> list[Incident]:
        rows = sorted(self._all("INCIDENT"), key=lambda r: r["opened_at"], reverse=True)
        return [Incident.model_validate_json(row["document"]) for row in rows]

    # --- seeding -------------------------------------------------------------

    def seeded(self, version: str = SEED_VERSION) -> bool:
        """Whether this table already holds the scripted scenarios.

        Without this every cold start would seed again. In memory that was
        harmless — the process had nothing — but against a durable table it
        would append the same audit trail on every container start until the
        page was a wall of duplicates.
        """
        return bool(self.table.get_item(Key={"PK": self._pk("META"), "SK": f"SEED#{version}"}).get("Item"))

    def mark_seeded(self, version: str = SEED_VERSION, detail: dict | None = None) -> None:
        self.table.put_item(
            Item={
                "PK": self._pk("META"),
                "SK": f"SEED#{version}",
                "at": datetime.now().astimezone().isoformat(),
                "detail": _numbers_to_decimal(detail or {}),
            }
        )

    def clear(self, partitions: Iterable[str] = (
        "INCIDENT", "AUDIT", "EVENT", "NODE", "EDGE", "META", "CHAT",
    )) -> int:
        """Empty the table. For re-seeding after the scenarios change shape."""
        removed = 0
        for partition in partitions:
            rows = self._all(partition)
            with self.table.batch_writer() as batch:
                for row in rows:
                    batch.delete_item(Key={"PK": row["PK"], "SK": row["SK"]})
                    removed += 1
        return removed

    # --- chat answer cache ---------------------------------------------------

    def get_cached_answer(self, digest: str) -> dict | None:
        row = self.table.get_item(Key={"PK": self._pk("CHAT"), "SK": digest}).get("Item")
        return _plain(row.get("answer")) if row else None

    def put_cached_answer(self, digest: str, answer: dict) -> None:
        self.table.put_item(
            Item={
                "PK": self._pk("CHAT"),
                "SK": digest,
                "answer": _numbers_to_decimal(answer),
                "at": datetime.now().astimezone().isoformat(),
            }
        )

    def recent_events(self, sources: list[str] | None = None, limit: int = 50) -> list[dict]:
        """Newest events, optionally from named sources.

        Filtered here rather than by the caller because the alternative is
        fetching the whole partition into the API and discarding most of it —
        which works at twenty-four entries and stops working at the first real
        feed.
        """
        rows = self._all("EVENT")
        if sources:
            wanted = set(sources)
            rows = [row for row in rows if row.get("source") in wanted]
        rows.sort(key=lambda row: str(row.get("occurred_at", "")), reverse=True)
        # `_event_row`, not `_plain`. The row as stored carries the table's own
        # keys and holds payload, provenance and labels as JSON strings; the
        # normaliser is what turns it back into the shape every other read
        # returns. Skipping it published `PK`, `GSI1PK` and the namespace to
        # anyone calling the route, and handed them three fields to parse
        # themselves.
        return [self._event_row(row) for row in rows[:limit]]

    # --- threat feed cursors -------------------------------------------------

    def get_feed_cursor(self, feed: str) -> str | None:
        row = self.table.get_item(
            Key={"PK": self._pk("META"), "SK": f"FEED#{feed}"}
        ).get("Item")
        return str(row["cursor"]) if row and row.get("cursor") else None

    def set_feed_cursor(self, feed: str, value: str) -> None:
        self.table.put_item(
            Item={
                "PK": self._pk("META"),
                "SK": f"FEED#{feed}",
                "cursor": value,
                "at": datetime.now().astimezone().isoformat(),
            }
        )
