"""Blast radius, expressed as a walk somebody can check.

Deliberately **not** in `testgraph.py`, which is skipped wholesale when Postgres
is unreachable. Nothing here needs a database — the graph is a fixture — and a
test that silently does not run is worse than one that does not exist, because
it reports green.
"""

from __future__ import annotations

# --- blast radius as a drawable walk (R63) ----------------------------------


class _Snapshot:
    """A graph with one cited path and one uncited shortcut.

    The shortcut is the point of the fixture: it reaches a real entity, so a
    walk that ignores citations would find it and draw it, and the drawing would
    assert a relationship with nothing behind it.
    """

    NODES = [
        {"key": "host:a", "name": "a", "kind": "host", "estimated_users": 0},
        {"key": "host:b", "name": "b", "kind": "host", "estimated_users": 3},
        {"key": "host:c", "name": "c", "kind": "host", "estimated_users": 0},
        {"key": "host:z", "name": "z", "kind": "host", "estimated_users": 0},
    ]
    EDGES = [
        {"source": "host:a", "target": "host:b", "kind": "talks_to", "evidence": ["EV-1"]},
        {"source": "host:b", "target": "host:c", "kind": "talks_to", "evidence": ["EV-2"]},
        # No evidence. Reaches a genuinely affected entity, and must not be used.
        {"source": "host:a", "target": "host:z", "kind": "assumed", "evidence": []},
    ]

    def snapshot(self, limit: int = 400) -> dict:
        return {"nodes": self.NODES, "edges": self.EDGES}


def _walk(monkeypatch, affected):
    from app.api import routes

    monkeypatch.setattr(routes, "GRAPH", _Snapshot())
    return routes._cited_paths("host:a", set(affected), max_depth=10)


def test_an_uncited_edge_is_never_traversed(monkeypatch) -> None:
    """R50's rule, enforced in the walk rather than at render time.

    Filtering when drawing would leave `host:z` reachable and the reason
    invisible — the node appears, the edge does not, and the picture asserts a
    relationship nobody can check. Refusing the hop puts the rule one layer
    earlier, where it cannot be forgotten by the next component to draw this.
    """
    reached, edges = _walk(monkeypatch, ["host:b", "host:c", "host:z"])
    keys = {row["key"] for row in reached}
    assert "host:z" not in keys, "crossed an edge carrying no evidence"
    assert keys == {"host:b", "host:c"}


def test_every_drawn_edge_carries_its_citations(monkeypatch) -> None:
    _, edges = _walk(monkeypatch, ["host:b", "host:c", "host:z"])
    assert edges
    for edge in edges:
        assert edge["evidence"], edge


def test_depth_is_the_number_of_hops(monkeypatch) -> None:
    """The view is radial, so a ring per hop has to be a fact rather than
    something a reader infers from arrow direction."""
    reached, _ = _walk(monkeypatch, ["host:b", "host:c"])
    depths = {row["key"]: row["depth"] for row in reached}
    assert depths == {"host:b": 1, "host:c": 2}


def test_the_walk_stays_inside_the_authoritative_set(monkeypatch) -> None:
    """`affected` comes from the graph function risk scoring uses. The walk
    illustrates that set; it must not enlarge it, or the picture and the score
    would be answering different questions."""
    reached, _ = _walk(monkeypatch, ["host:b"])
    assert {row["key"] for row in reached} == {"host:b"}


def test_what_could_not_be_drawn_is_reported_rather_than_dropped(monkeypatch) -> None:
    """A node in the reach that no cited edge explains is still in the list.
    Silently omitting it would make the drawing disagree with the count beside
    it, and the reader would trust whichever they saw first."""
    from app.api import routes

    monkeypatch.setattr(routes, "GRAPH", _Snapshot())

    class _Radius:
        origin = "host:a"
        affected = ["host:b", "host:c", "host:z"]
        entity_count = 3
        estimated_users = 3

    monkeypatch.setattr(
        routes.GRAPH, "blast_radius", lambda *a, **k: _Radius(), raising=False
    )
    out = routes.blast_radius("host:a")
    assert out["uncited"] == ["host:z"]
    assert out["entity_count"] == 3
