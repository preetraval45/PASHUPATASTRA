"""Correlation.

Most of these tests are about the merge that should *not* happen. Splitting one
incident in two costs an operator a little confusion; merging two into one gives
them a fabricated causal chain and an inflated blast radius — and blast radius
feeds risk, so a bad merge can widen what the system is permitted to do.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pashupatastra import EntityKind, EntityRef, Node, Severity, TopologyGraph
from pashupatastra.correlation import Correlator, measure_merges
from pashupatastra.detection import Finding
from pashupatastra.topology import Edge

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)


def graph() -> TopologyGraph:
    """frontend → api → {postgres, redis};  billing and search are unconnected."""
    g = TopologyGraph()
    for kind, name, users in [
        (EntityKind.DATABASE, "postgres", 0),
        (EntityKind.CACHE, "redis", 0),
        (EntityKind.SERVICE, "api", 0),
        (EntityKind.SERVICE, "frontend", 1200),
        (EntityKind.SERVICE, "billing", 300),
        (EntityKind.SERVICE, "search", 50),
    ]:
        g.add_node(Node(ref=EntityRef(kind=kind, id=name, name=name), estimated_users=users))
    g.add_edge(Edge(source="service:api", target="database:postgres"))
    g.add_edge(Edge(source="service:api", target="cache:redis"))
    g.add_edge(Edge(source="service:frontend", target="service:api"))
    return g


def finding(entity: str, signal: str = "cpu", seconds: int = 0, confidence: float = 0.5) -> Finding:
    return Finding(
        entity_key=entity,
        signal=signal,
        at=NOW + timedelta(seconds=seconds),
        value=99.0,
        baseline=40.0,
        deviation=7.0,
        direction="high",
        confidence=confidence,
        source="baseline",
        evidence=[f"evt-{entity}-{signal}-{seconds}"],
        severity=Severity.CRITICAL,
    )


@pytest.fixture
def correlator() -> Correlator:
    return Correlator(adjacency=graph())


def test_no_findings_yields_no_incidents(correlator: Correlator) -> None:
    result = correlator.correlate([])
    assert result.clusters == []
    assert result.compression_ratio == 0.0


def test_adjacent_and_close_in_time_becomes_one_incident(correlator: Correlator) -> None:
    """The product's opening claim: five signals, one incident."""
    result = correlator.correlate(
        [
            finding("database:postgres", "connections", 0),
            finding("service:api", "latency", 30),
            finding("service:api", "errors", 45),
            finding("service:frontend", "errors", 60),
        ]
    )
    assert len(result.clusters) == 1
    assert result.compression_ratio == 4.0


def test_unrelated_services_stay_separate_despite_identical_timing(
    correlator: Correlator,
) -> None:
    """The failure mode time-only correlation causes: in a busy system several
    unrelated things degrade in the same minute constantly, and merging them
    invents a causal story across services that have never spoken."""
    result = correlator.correlate(
        [finding("service:billing", seconds=0), finding("service:search", seconds=1)]
    )
    assert len(result.clusters) == 2


def test_adjacent_but_distant_in_time_stays_separate(correlator: Correlator) -> None:
    """Two failures on connected services a week apart are two incidents."""
    result = correlator.correlate(
        [
            finding("database:postgres", seconds=0),
            finding("service:api", seconds=7 * 24 * 3600),
        ]
    )
    assert len(result.clusters) == 2


def test_same_entity_failing_two_ways_is_one_incident(correlator: Correlator) -> None:
    """CPU saturation and rising latency on one service are two views of a
    single problem."""
    result = correlator.correlate(
        [finding("service:api", "cpu", 0), finding("service:api", "latency", 20)]
    )
    assert len(result.clusters) == 1


def test_grouping_is_transitive_along_a_propagation_chain(correlator: Correlator) -> None:
    """postgres and frontend are three hops apart, but a failure propagating
    along the chain is one incident — and the chain is what makes it one."""
    result = correlator.correlate(
        [
            finding("database:postgres", seconds=0),
            finding("service:api", seconds=20),
            finding("service:frontend", seconds=40),
        ]
    )
    assert len(result.clusters) == 1
    assert result.clusters[0].entities == {
        "database:postgres",
        "service:api",
        "service:frontend",
    }


def test_unknown_relationships_default_to_separate_incidents() -> None:
    """When the graph knows nothing, the answer is two incidents. Splitting
    costs a little confusion; merging costs a false causal chain."""
    empty = Correlator(adjacency=TopologyGraph())
    result = empty.correlate(
        [finding("service:a", seconds=0), finding("service:b", seconds=5)]
    )
    assert len(result.clusters) == 2


def test_depth_limit_bounds_adjacency() -> None:
    """At enough hops everything in a connected system reaches everything else,
    and an adjacency test that always says yes is not a test."""
    shallow = Correlator(adjacency=graph(), max_depth=1)
    result = shallow.correlate(
        [finding("database:postgres", seconds=0), finding("service:frontend", seconds=10)]
    )
    assert len(result.clusters) == 2


def test_cluster_inherits_the_full_evidence_trail(correlator: Correlator) -> None:
    """The incident must cite every event behind it, not only the trigger's."""
    result = correlator.correlate(
        [
            finding("database:postgres", "connections", 0),
            finding("service:api", "latency", 30),
        ]
    )
    assert len(result.clusters[0].evidence) == 2


def test_cluster_confidence_is_the_strongest_finding(correlator: Correlator) -> None:
    """Averaging would let weak corroborating signals dilute the strong one that
    justifies acting."""
    result = correlator.correlate(
        [
            finding("database:postgres", "connections", 0, confidence=0.9),
            finding("service:api", "latency", 10, confidence=0.2),
        ]
    )
    assert result.clusters[0].confidence == 0.9


def test_compression_ratio_is_reported(correlator: Correlator) -> None:
    result = correlator.correlate(
        [
            finding("database:postgres", "connections", 0),
            finding("service:api", "latency", 10),
            finding("service:api", "errors", 20),
            finding("service:billing", "errors", 25),
        ]
    )
    assert result.summary() == {"findings": 4, "incidents": 2, "compression_ratio": 2.0}


def test_clusters_are_ordered_by_onset(correlator: Correlator) -> None:
    result = correlator.correlate(
        [finding("service:search", seconds=300), finding("service:billing", seconds=0)]
    )
    assert result.clusters[0].entities == {"service:billing"}


# --- merge quality -----------------------------------------------------------


def test_perfect_clustering_scores_no_errors(correlator: Correlator) -> None:
    truth = {
        "database:postgres": "INC-1",
        "service:api": "INC-1",
        "service:billing": "INC-2",
        "service:search": "INC-2",
    }
    result = correlator.correlate(
        [
            finding("database:postgres", seconds=0),
            finding("service:api", seconds=10),
        ]
    )
    quality = measure_merges(result.clusters, lambda f: truth[f.entity_key])
    assert quality.incorrect_merges == 0
    assert quality.accuracy == 1.0


def test_incorrect_merge_is_counted() -> None:
    """A graph that wrongly connects two services produces exactly the error
    this metric exists to catch."""
    wrong = TopologyGraph()
    for name in ("billing", "search"):
        wrong.add_node(Node(ref=EntityRef(kind=EntityKind.SERVICE, id=name, name=name)))
    wrong.add_edge(Edge(source="service:billing", target="service:search"))

    result = Correlator(adjacency=wrong).correlate(
        [finding("service:billing", seconds=0), finding("service:search", seconds=5)]
    )
    assert len(result.clusters) == 1

    truth = {"service:billing": "INC-1", "service:search": "INC-2"}
    quality = measure_merges(result.clusters, lambda f: truth[f.entity_key])
    assert quality.incorrect_merges == 1
    assert quality.incorrect_merge_rate == 1.0


def test_incorrect_split_is_counted_separately(correlator: Correlator) -> None:
    """Reported apart from merges because they are not equally bad: a merge
    invents causality and inflates blast radius; a split costs a second tab."""
    result = correlator.correlate(
        [finding("service:billing", seconds=0), finding("service:search", seconds=5)]
    )
    truth = {"service:billing": "INC-1", "service:search": "INC-1"}
    quality = measure_merges(result.clusters, lambda f: truth[f.entity_key])

    assert quality.incorrect_splits == 1
    assert quality.incorrect_merges == 0


def test_merge_quality_of_a_single_finding_is_vacuous(correlator: Correlator) -> None:
    result = correlator.correlate([finding("service:api")])
    quality = measure_merges(result.clusters, lambda f: "INC-1")
    assert quality.total_pairs == 0
    assert quality.accuracy == 0.0
