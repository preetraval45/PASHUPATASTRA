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

from pashupatastra import Edge, EntityKind, EntityRef, IncidentState, Node
from pashupatastra.scenarios import Scenario, load_scenarios

from .demoincidents import scenarios as security_scenarios
from .engines.audit import AUDIT, AuditKind, AuditRecord

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
    make the map look busier.

    Edges come from the scenarios too, and only the ones their own evidence
    establishes (R50). This used to add none at all, on the reasoning that a
    plausible topology drawn from co-occurrence would put fabricated structure
    behind blast radius — which was right about the danger and wrong about the
    remedy. The map was a row of disconnected boxes and blast radius returned
    nothing, so `isolate_host` scored its risk against an estate of one. The
    answer is not "no edges", it is "no edge without a citation": every path
    names the events that establish it, and `testaccesspaths.py` fails on any
    that cannot.
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

    edges = [edge for scenario in scenarios for edge in scenario.access]
    graph.upsert_edges(edges)

    events = [event for scenario in scenarios for event in scenario.events(now)]
    store.save_events(events)
    for scenario in scenarios:
        incidents.save(scenario.incident)
        _audit(scenario, now)

    return {
        "incidents": len(scenarios),
        "entities": len(entities),
        "edges": len(edges),
        "events": len(events),
        "audit_records": len(AUDIT),
    }


def _audit(scenario, now: datetime) -> None:
    """Write the trail the scenario implies, derived from the scenario itself.

    Each incident already carries transitions — detected, correlated, diagnosed,
    awaiting a decision — and each transition names an actor and a justification.
    Writing audit records from those rather than composing a second story keeps
    the timeline and the audit page from disagreeing about what happened.

    Every record says which scenario produced it, so nothing here can be read as
    something the system observed.
    """
    incident = scenario.incident

    for signal in scenario.signals:
        AUDIT.append(
            AuditRecord(
                at=now + timedelta(seconds=signal.at_offset_seconds),
                kind=AuditKind.OBSERVATION,
                actor="drishti",
                incident_ref=incident.id,
                summary=signal.message,
                detail={"event_id": signal.id, "scenario": incident.id},
            )
        )

    for hypothesis in incident.hypotheses:
        # The alternatives are recorded too. A trail that keeps only the answer
        # cannot show that anything else was considered, and "what else did it
        # think" is the first question anyone asks of a diagnosis.
        ruled_out = " · ruled out by " + ", ".join(hypothesis.contradicted_by) if hypothesis.contradicted_by else ""
        AUDIT.append(
            AuditRecord(
                at=incident.opened_at,
                kind=AuditKind.HYPOTHESIS,
                actor="buddhi",
                incident_ref=incident.id,
                summary=f"{hypothesis.statement} ({hypothesis.confidence:.0%}){ruled_out}",
                detail={"evidence": hypothesis.evidence, "scenario": incident.id},
            )
        )

    for transition in incident.transitions:
        AUDIT.append(
            AuditRecord(
                at=transition.at,
                kind=(
                    AuditKind.ESCALATION
                    if transition.to_state is IncidentState.ESCALATED
                    else AuditKind.POLICY_EVALUATION
                    if transition.actor == "dharma"
                    else AuditKind.OBSERVATION
                ),
                actor=transition.actor,
                incident_ref=incident.id,
                summary=f"{transition.to_state.value.replace('_', ' ')} — {transition.justification}",
                detail={"from": transition.from_state, "scenario": incident.id},
            )
        )


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
