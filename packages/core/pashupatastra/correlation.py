"""Correlation — many findings, one incident.

The product's opening claim is that five alerts become one incident. This is
where that happens, and the way it can go wrong is worse than the problem it
solves.

**Two gates, both required: topology adjacency AND time proximity.**

Time alone is the naive implementation and it is actively harmful. In a busy
system several unrelated things degrade within the same minute constantly, and
merging them produces one incident with a fabricated causal story spanning
services that have never spoken. An operator then chases a relationship that
does not exist, and — worse — blast radius is computed across the union, which
inflates estimated impact and can escalate an action past the autonomy it should
have had.

Adjacency alone is equally wrong: two failures on the same service a week apart
are two incidents.

So findings merge only when the graph connects them *and* they are close in
time. When the graph does not know a relationship exists, the answer is two
incidents — the conservative direction, because splitting one incident in two
costs an operator a little confusion, while merging two into one costs them a
false causal chain.

**Merging is directional evidence, not proof.** A merge says "these look
related"; it does not say which caused which. Ordering the chain is Buddhi's
job, and it needs the deployment timeline that correlation deliberately does not
consult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Protocol

from .detection import Finding

DEFAULT_WINDOW = timedelta(minutes=5)
"""How close in time two findings must be to be candidates.

Five minutes is a judgement, not a derivation: long enough that a failure
propagating through three hops still lands inside it, short enough that a
morning's unrelated blips do not chain together. It is a tunable that the
benchmark should settle."""

DEFAULT_MAX_DEPTH = 3
"""How far apart in the graph two entities may be and still count as adjacent.

Bounded because at enough hops everything in a connected system reaches
everything else, and an adjacency test that always says yes is not a test."""


class Adjacency(Protocol):
    """Whatever can answer 'are these two entities connected?'.

    A protocol rather than a concrete graph so correlation can be tested without
    a database and run against either the in-memory reference or Postgres —
    both of which are already proven to agree (Graph ADR).
    """

    def adjacent(self, a: str, b: str, max_depth: int = 3) -> bool: ...


@dataclass
class Cluster:
    """A group of findings believed to be one incident."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def entities(self) -> set[str]:
        return {f.entity_key for f in self.findings}

    @property
    def first_seen(self) -> datetime:
        return min(f.at for f in self.findings)

    @property
    def last_seen(self) -> datetime:
        return max(f.at for f in self.findings)

    @property
    def evidence(self) -> list[str]:
        """Every event behind every finding, so the incident inherits the full
        citation trail rather than only the trigger's."""
        seen: list[str] = []
        for finding in self.findings:
            for event_id in finding.evidence:
                if event_id not in seen:
                    seen.append(event_id)
        return seen

    @property
    def confidence(self) -> float:
        """The strongest finding's confidence, not the average.

        Averaging would let a cluster of weak corroborating signals dilute one
        strong one — and it is the strong finding that justifies acting.
        """
        return max((f.confidence for f in self.findings), default=0.0)

    def describe(self) -> str:
        entities = sorted(self.entities)
        head = ", ".join(entities[:3])
        if len(entities) > 3:
            head += f" and {len(entities) - 3} more"
        return f"{len(self.findings)} findings across {head}"


@dataclass
class CorrelationResult:
    clusters: list[Cluster]
    findings_in: int

    @property
    def compression_ratio(self) -> float:
        """Findings per resulting incident.

        The headline number for "five alerts became one incident" — and one that
        must be read next to the incorrect-merge rate, because compression is
        trivially maximized by merging everything into a single incident.
        """
        return (
            round(self.findings_in / len(self.clusters), 2)
            if self.clusters
            else 0.0
        )

    def summary(self) -> dict[str, object]:
        return {
            "findings": self.findings_in,
            "incidents": len(self.clusters),
            "compression_ratio": self.compression_ratio,
        }


class Correlator:
    def __init__(
        self,
        adjacency: Adjacency,
        window: timedelta = DEFAULT_WINDOW,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> None:
        self.adjacency = adjacency
        self.window = window
        self.max_depth = max_depth

    def correlate(self, findings: list[Finding]) -> CorrelationResult:
        """Group findings into clusters.

        Union-find over the pairwise relation, so grouping is transitive: if A
        relates to B and B to C, all three are one incident even when A and C are
        four hops apart. That is intended — a failure propagating along a chain
        is one incident, and the chain is exactly what makes it one.
        """
        if not findings:
            return CorrelationResult(clusters=[], findings_in=0)

        ordered = sorted(findings, key=lambda f: f.at)
        parent = list(range(len(ordered)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            a, b = find(i), find(j)
            if a != b:
                parent[b] = a

        for i, left in enumerate(ordered):
            for j in range(i + 1, len(ordered)):
                right = ordered[j]
                # Sorted by time, so once the gap exceeds the window every
                # later finding is also out of range.
                if right.at - left.at > self.window:
                    break
                if self._related(left, right):
                    union(i, j)

        grouped: dict[int, Cluster] = {}
        for index, finding in enumerate(ordered):
            grouped.setdefault(find(index), Cluster()).findings.append(finding)

        clusters = sorted(grouped.values(), key=lambda c: c.first_seen)
        return CorrelationResult(clusters=clusters, findings_in=len(findings))

    def _related(self, left: Finding, right: Finding) -> bool:
        """Both gates. Neither alone is sufficient."""
        if left.entity_key == right.entity_key:
            # The same entity failing two ways within the window is one
            # incident: CPU saturation and rising latency on one service are two
            # views of a single problem.
            return True
        return self.adjacency.adjacent(left.entity_key, right.entity_key, self.max_depth)


# --- measurement -------------------------------------------------------------


@dataclass
class MergeQuality:
    """How well clustering matched a known-correct grouping.

    Reported as two separate failure modes rather than one accuracy number,
    because they are not equally bad. An incorrect merge invents a causal
    relationship and inflates blast radius; an incorrect split costs an operator
    a second browser tab.
    """

    incorrect_merges: int = 0
    """Pairs grouped together that belong to different true incidents."""

    incorrect_splits: int = 0
    """Pairs separated that belong to the same true incident."""

    correct_pairs: int = 0
    total_pairs: int = 0

    @property
    def incorrect_merge_rate(self) -> float:
        return (
            round(self.incorrect_merges / self.total_pairs, 4)
            if self.total_pairs
            else 0.0
        )

    @property
    def incorrect_split_rate(self) -> float:
        return (
            round(self.incorrect_splits / self.total_pairs, 4)
            if self.total_pairs
            else 0.0
        )

    @property
    def accuracy(self) -> float:
        return (
            round(self.correct_pairs / self.total_pairs, 4) if self.total_pairs else 0.0
        )

    def summary(self) -> dict[str, object]:
        return {
            "incorrect_merge_rate": self.incorrect_merge_rate,
            "incorrect_split_rate": self.incorrect_split_rate,
            "accuracy": self.accuracy,
            "pairs": self.total_pairs,
        }


def measure_merges(
    clusters: list[Cluster], truth: Callable[[Finding], str]
) -> MergeQuality:
    """Score clustering against ground truth.

    `truth` maps a finding to the incident it really belongs to — from a
    benchmark scenario, authored before the correlator ran.

    Pairwise rather than cluster-by-cluster, because cluster identity is
    arbitrary: what matters is whether two findings that belong together ended
    up together, not what their group was called.
    """
    quality = MergeQuality()
    labelled = [(f, truth(f)) for cluster in clusters for f in cluster.findings]
    membership = {
        id(f): index for index, cluster in enumerate(clusters) for f in cluster.findings
    }

    for i in range(len(labelled)):
        for j in range(i + 1, len(labelled)):
            (left, left_truth), (right, right_truth) = labelled[i], labelled[j]
            same_cluster = membership[id(left)] == membership[id(right)]
            same_truth = left_truth == right_truth

            quality.total_pairs += 1
            if same_cluster and same_truth:
                quality.correct_pairs += 1
            elif not same_cluster and not same_truth:
                quality.correct_pairs += 1
            elif same_cluster and not same_truth:
                quality.incorrect_merges += 1
            else:
                quality.incorrect_splits += 1

    return quality
