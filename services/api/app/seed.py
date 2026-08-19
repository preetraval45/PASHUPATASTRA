"""Replay the labelled scenario corpus into the graph, for demo deployments.

A deployment with no connectors has an empty topology, and an empty topology
renders an empty dashboard. This fills it from `benchmark/incidents/` — the same
corpus `scripts/benchphase2.py` scores against — rather than from hand-written
fixtures, so what the map shows is telemetry the repository already committed to
and can be checked against.

Three things this deliberately does not do.

It **invents no dependencies**. Corpus scenarios declare entities and signals,
not topology. The only edges seeded are the ones the demo incident already
asserts in its causal chain; deriving a plausible-looking service graph from
co-occurrence would put fabricated structure behind blast radius, which is an
input to risk scoring.

It **invents no user counts**. `estimated_users` stays zero for corpus entities
because nothing in the corpus measures it. A blast radius of zero users is
visibly wrong to a reader; a blast radius of an invented 4,000 is not.

It **relabels nothing**. Every event keeps `source_system="scenario"` and the
scenario id in its provenance, so no view can present replayed telemetry as
something observed from a live system.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from pashupatastra import Edge, EntityKind, EntityRef, Node
from pashupatastra.scenarios import Scenario, load_scenarios

from .demoincidents import scenarios as security_scenarios

def _corpus() -> Path:
    """Locate `benchmark/incidents/` by walking up from this module.

    A fixed number of `.parents` hops is right for the repository layout and
    wrong for a deployment bundle, where the package sits at the archive root.
    Searching upward is correct for both.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "benchmark" / "incidents"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "benchmark/incidents/ not found — the scenario corpus was not bundled"
    )


CORPUS = None
"""Resolved lazily by `seed`, so importing this module never depends on layout."""

LATEST_SIGNAL_AGO = timedelta(minutes=4)
"""How long ago the newest replayed signal should appear to have arrived.

The corpus is anchored to a fixed epoch so results are reproducible. Seeding at
that epoch would date every event months into the past, and the map's severity
rollup only looks back fifteen minutes — a demo that replayed the corpus
verbatim would show a graph of uniformly grey, long-dead entities.
"""

DEMO_EDGES = (
    ("service:frontend", "service:checkout-api"),
    ("service:checkout-api", "database:postgres-primary"),
)
"""The dependencies the demo incident already claims in its causal chain and
impact — `frontend` and `checkout-api` degrade when `postgres-primary` does.
Seeded so blast radius has something true to walk, and nothing beyond it."""


def _ref(key: str) -> EntityRef:
    kind, _, entity_id = key.partition(":")
    return EntityRef(kind=EntityKind(kind), id=entity_id, name=entity_id)


def _origin(scenario: Scenario, now: datetime) -> datetime:
    """Shift the scenario so its last signal lands `LATEST_SIGNAL_AGO` ago.

    Intervals between signals are preserved: correlation groups on time
    proximity, so compressing or stretching them would change what the corpus
    means.
    """
    span = max((s.at_seconds for s in scenario.signals), default=0.0)
    return now - LATEST_SIGNAL_AGO - timedelta(seconds=span)


def seed_security(graph, store, incidents, now: datetime | None = None) -> dict[str, int]:
    """Load the written blue-team scenarios, their entities and their telemetry.

    Order matters. Entities, then events, then incidents: an incident rendered
    before its citations exist shows references that resolve to nothing, and a
    citation that dangles for even one request is the defect this ordering
    exists to prevent.

    Entities come from the scenarios themselves — every entity an incident names
    in its causal chain, its affected list, or an event. Nothing is invented to
    make the map look busier, and no edges are added at all: the scenarios
    declare a sequence of events, not a dependency graph, and a plausible
    topology drawn from co-occurrence would put fabricated structure behind
    blast radius.
    """
    now = now or datetime.now().astimezone()
    scenarios = security_scenarios(now)

    entities: dict[str, EntityRef] = {}
    for scenario in scenarios:
        for ref in scenario.incident.affected_entities:
            entities[ref.key()] = ref
        for link in scenario.incident.causal_chain:
            entities[link.entity.key()] = link.entity
        for signal in scenario.signals:
            entities[signal.entity.key()] = signal.entity

    graph.upsert_nodes([Node(ref=ref, owner=None, estimated_users=0) for ref in entities.values()])

    events = [event for scenario in scenarios for event in scenario.events(now)]
    store.save_events(events)
    for scenario in scenarios:
        incidents.save(scenario.incident)

    return {
        "incidents": len(scenarios),
        "entities": len(entities),
        "events": len(events),
    }


def seed(graph, store, corpus: Path | str | None = None, now: datetime | None = None) -> dict[str, int]:
    """Load the corpus into the graph and the event store. Returns what was written.

    Both are passed in rather than resolved here: with no database they are the
    same in-memory object, with one they are not, and seeding should not be the
    place that decides which.
    """
    now = now or datetime.now().astimezone()
    scenarios = load_scenarios(corpus or _corpus())

    events = [
        event
        for scenario in scenarios
        for event in scenario.events(origin=_origin(scenario, now))
    ]

    nodes = {
        event.entity_ref.key(): Node(ref=event.entity_ref, owner=None, estimated_users=0)
        for event in events
    }
    for source, target in DEMO_EDGES:
        for key in (source, target):
            nodes.setdefault(key, Node(ref=_ref(key), owner=None, estimated_users=0))

    graph.upsert_nodes(list(nodes.values()))
    graph.upsert_edges([Edge(source=s, target=t) for s, t in DEMO_EDGES])
    store.save_events(events)

    return {
        "scenarios": len(scenarios),
        "entities": len(nodes),
        "events": len(events),
        "edges": len(DEMO_EDGES),
    }
