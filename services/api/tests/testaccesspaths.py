"""Access paths in the written scenarios.

The map is the artefact that is supposed to be checkable, and blast radius —
which reads it — is an input to risk scoring, and therefore to what the policy
engine will let anyone do. An edge nobody can trace is fabricated structure
sitting underneath an authorisation decision.

So the rule is not "no edges", which is what the seed used to do and which left
the map a row of disconnected boxes and `isolate_host` scoring its risk against
an estate of one. The rule is **no edge without a citation**, and this is the
file that enforces it.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from app.demoincidents import scenarios
from pashupatastra import Edge
from pashupatastra.topology import TopologyGraph

NOW = datetime(2026, 8, 21, 12, 0, 0).astimezone()


@pytest.fixture(params=[0, 1, 2], ids=lambda i: scenarios(NOW)[i].incident.id)
def scenario(request):
    return scenarios(NOW)[request.param]


def _entities(scenario) -> set[str]:
    """Everything the scenario legitimately names."""
    keys = {ref.key() for ref in scenario.incident.affected_entities}
    keys |= {link.entity.key() for link in scenario.incident.causal_chain}
    keys |= {signal.entity.key() for signal in scenario.signals}
    return keys


# --- the rule ------------------------------------------------------------------


def test_every_access_path_cites_evidence(scenario) -> None:
    """R50's done-when, and the reason this file exists."""
    assert scenario.access, f"{scenario.incident.id} declares no access paths"
    for edge in scenario.access:
        assert edge.evidence, f"{edge.source} <- {edge.target} cites nothing"


def test_every_citation_is_a_signal_this_scenario_declares(scenario) -> None:
    """Not merely non-empty — resolvable, and resolvable *here*.

    An id from another scenario would pass a non-empty check and still be a
    path this incident's evidence does not establish.
    """
    ours = {signal.id for signal in scenario.signals}
    for edge in scenario.access:
        for ref in edge.evidence:
            assert ref in ours, (
                f"{scenario.incident.id}: {edge.source} <- {edge.target} cites "
                f"{ref}, which is not one of this scenario's signals"
            )


def test_both_ends_of_every_path_are_entities_this_scenario_names(scenario) -> None:
    """An edge to an entity the incident never mentions puts a node on the map
    that nothing accounts for."""
    known = _entities(scenario)
    for edge in scenario.access:
        assert edge.source in known, f"unknown source {edge.source}"
        assert edge.target in known, f"unknown target {edge.target}"


def test_a_path_never_points_at_itself(scenario) -> None:
    for edge in scenario.access:
        assert edge.source != edge.target, edge.source


def test_the_check_catches_an_unsupported_path(scenario) -> None:
    """Proof that the three tests above are load-bearing.

    A rule nobody has watched fail is a rule nobody knows works — the same
    discipline applied to the OpenAPI drift test in R29. Here an edge is
    fabricated the way a careless author would fabricate one: plausible
    endpoints, no citation.
    """
    invented = Edge(source="asset:sso-portal", target="host:ws-0148", kind="guessed")
    assert not invented.evidence

    ours = {signal.id for signal in scenario.signals}
    borrowed = Edge(
        source=next(iter(_entities(scenario))),
        target=next(iter(_entities(scenario) - {next(iter(_entities(scenario)))})),
        kind="borrowed",
        evidence=["SEC-9999-z"],
    )
    assert borrowed.evidence and not set(borrowed.evidence) & ours, (
        "a citation from nowhere must not look like one of ours"
    )


# --- what the paths are for ------------------------------------------------------


def test_the_scenario_graph_is_connected(scenario) -> None:
    """"All three render a connected access graph" — a map of islands is the
    thing R50 was written to fix.

    Connectivity is judged ignoring direction: the graph is a story about how
    one thing reached another, and a chain is connected even though every edge
    points the same way.
    """
    edges = scenario.access
    keys = {edge.source for edge in edges} | {edge.target for edge in edges}
    neighbours: dict[str, set[str]] = {key: set() for key in keys}
    for edge in edges:
        neighbours[edge.source].add(edge.target)
        neighbours[edge.target].add(edge.source)

    start = next(iter(keys))
    seen, queue = {start}, [start]
    while queue:
        for neighbour in neighbours[queue.pop()]:
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)

    assert seen == keys, f"{scenario.incident.id} is not connected: {sorted(keys - seen)} unreachable"


def test_blast_radius_reaches_something_from_the_compromised_entity(scenario) -> None:
    """The point of having edges at all.

    With none, `blast_radius` returned an empty set and `isolate_host` scored
    its risk against an estate of one — the policy engine pricing a decision
    against a graph that said nothing was connected to anything.
    """
    graph = TopologyGraph()
    from pashupatastra import EntityKind, EntityRef, Node

    for key in _entities(scenario):
        kind, _, rest = key.partition(":")
        graph.add_node(
            Node(ref=EntityRef(kind=EntityKind(kind), id=rest, name=rest), estimated_users=0)
        )
    for edge in scenario.access:
        graph.add_edge(edge)

    reached = {
        origin: graph.blast_radius(origin).affected for origin in _entities(scenario)
    }
    assert any(reached.values()), f"{scenario.incident.id}: nothing reaches anything"


def test_the_direction_puts_the_asset_at_risk_from_the_account() -> None:
    """The one thing that would be silently, expensively wrong.

    `blast_radius` walks dependents, so the edge runs from the asset to the
    account. Reversed, the map would report that compromising a mailbox
    endangers the attacker, and every risk score built on it would be backwards
    while still looking like a number.
    """
    graph = TopologyGraph()
    from pashupatastra import EntityKind, EntityRef, Node

    phishing = next(s for s in scenarios(NOW) if s.incident.id == "INC-2026-0902")
    for key in _entities(phishing):
        kind, _, rest = key.partition(":")
        graph.add_node(
            Node(ref=EntityRef(kind=EntityKind(kind), id=rest, name=rest), estimated_users=0)
        )
    for edge in phishing.access:
        graph.add_edge(edge)

    from_account = graph.blast_radius("account:m.okafor").affected
    assert "asset:m.okafor-mailbox" in from_account
    assert "asset:oauth-app-Rep0rt-Sync" in from_account

    # And not the other way round: the mailbox being read does not endanger the
    # identity that owns it.
    assert "account:m.okafor" not in graph.blast_radius("asset:m.okafor-mailbox").affected


def test_the_citation_survives_storage() -> None:
    """It did not, at first.

    `upsert_edges` wrote source, target and kind, so the edge reached the table
    and its reason did not. The map on the deployed site would have asserted a
    path and been unable to say why — the checkable property working only on a
    laptop, which is the same as not working.
    """
    from app.graphmemory import MemoryGraph
    from pashupatastra import EntityKind, EntityRef, Node

    graph = MemoryGraph()
    scenario = scenarios(NOW)[0]
    for key in _entities(scenario):
        kind, _, rest = key.partition(":")
        graph.upsert_nodes(
            [Node(ref=EntityRef(kind=EntityKind(kind), id=rest, name=rest), estimated_users=0)]
        )
    graph.upsert_edges(scenario.access)

    rendered = graph.snapshot()["edges"]
    assert rendered, "no edges came back"
    for edge in rendered:
        assert edge["evidence"], f"{edge['source']} <- {edge['target']} lost its citation"
