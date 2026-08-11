"""Blast-radius latency benchmark.

Produces the measurement the Graph ADR requires: p50/p99 traversal latency
against the roadmap's 200ms exit criterion, on a graph shaped like a real
service topology (layered tiers, each node depending on a few in the tier below).

Usage:  python scripts/benchgraph.py [--nodes 4000] [--database-url URL]

Cleans up after itself; the synthetic nodes are prefixed `service:bench`.
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time

import psycopg
from psycopg.rows import dict_row

DEFAULT_URL = "postgresql://pashupatastra:pashupatastra@localhost:5433/pashupatastra"
TIERS = 6
TARGET_MS = 200


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", type=int, default=4000)
    parser.add_argument("--database-url", default=DEFAULT_URL)
    parser.add_argument("--keep", action="store_true", help="leave the synthetic graph in place")
    args = parser.parse_args()

    random.seed(7)  # deterministic: reruns are comparable
    with psycopg.connect(args.database_url, row_factory=dict_row) as conn:
        _clean(conn)
        tiers = _seed(conn, args.nodes)
        timings, sizes = _measure(conn, tiers)
        if not args.keep:
            _clean(conn)

    timings.sort()
    p = lambda q: timings[min(int(len(timings) * q), len(timings) - 1)]  # noqa: E731
    print(f"affected nodes: median {statistics.median(sizes):.0f}, max {max(sizes)}")
    print(f"p50 {statistics.median(timings):6.1f} ms")
    print(f"p95 {p(0.95):6.1f} ms")
    print(f"p99 {p(0.99):6.1f} ms   target < {TARGET_MS} ms")
    return 0 if p(0.99) < TARGET_MS else 1


def _clean(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM topology_edge WHERE source_key LIKE 'service:bench%'")
    conn.execute("DELETE FROM topology_node WHERE key LIKE 'service:bench%'")
    conn.commit()


def _seed(conn: psycopg.Connection, count: int) -> list[list[str]]:
    tiers: list[list[str]] = [[] for _ in range(TIERS)]
    nodes = []
    for i in range(count):
        key = f"service:bench{i}"
        tiers[i % TIERS].append(key)
        nodes.append((key, "service", f"bench{i}", f"bench{i}", random.randint(0, 200)))
    conn.cursor().executemany(
        "INSERT INTO topology_node (key, kind, entity_id, name, estimated_users)"
        " VALUES (%s,%s,%s,%s,%s) ON CONFLICT (key) DO NOTHING",
        nodes,
    )

    edges = []
    for tier in range(1, TIERS):
        for source in tiers[tier]:
            for target in random.sample(tiers[tier - 1], k=min(3, len(tiers[tier - 1]))):
                edges.append((source, target, "depends_on"))
    conn.cursor().executemany(
        "INSERT INTO topology_edge (source_key, target_key, kind)"
        " VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
        edges,
    )
    conn.commit()

    counts = conn.execute(
        "SELECT (SELECT count(*) FROM topology_node) AS n,"
        " (SELECT count(*) FROM topology_edge) AS e"
    ).fetchone()
    print(f"graph: {counts['n']} nodes, {counts['e']} edges")
    return tiers


def _measure(conn: psycopg.Connection, tiers: list[list[str]]) -> tuple[list[float], list[int]]:
    # Sample the deepest tier: the worst case, furthest from the leaves.
    samples = random.sample(tiers[0], min(60, len(tiers[0])))
    timings, sizes = [], []
    for key in samples:
        started = time.perf_counter()
        rows = conn.execute("SELECT affected_key FROM blast_radius(%s, 10)", (key,)).fetchall()
        timings.append((time.perf_counter() - started) * 1000)
        sizes.append(len(rows))
    return timings, sizes


if __name__ == "__main__":
    sys.exit(main())
