"""Run the Phase 2 loop over the labelled scenario corpus.

Exercises detection → correlation → recall against known-correct answers, and
reports failures before successes.

**What this measures, and what it does not.** Detection, correlation and memory
recall are real code and are genuinely scored here. *Reasoning quality is not.*
Top-1 root-cause accuracy — the actual Phase 2 exit criterion — needs a real
model, and running it against the deterministic stub would measure a fixture
this repository wrote. That number is deliberately absent rather than reported
as zero or, worse, as a pass.

**And this is not PIB.** The benchmark proper injects faults into a running
stack; this replays telemetry, which is cheaper and much less credible. Nothing
here should be quoted as a benchmark result.

Usage:  python scripts/benchphase2.py [--strict]

`--strict` exits non-zero on any false alarm or incorrect merge — the two
failures that are actively harmful rather than merely disappointing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta

sys.path.insert(0, "packages/core")

from pashupatastra.correlation import Correlator, measure_merges  # noqa: E402
from pashupatastra.detection import Detector  # noqa: E402
from pashupatastra.events import EventClass  # noqa: E402
from pashupatastra.scenarios import (  # noqa: E402
    CorpusResult,
    Scenario,
    ScenarioResult,
    load_scenarios,
)
from pashupatastra.smriti import (  # noqa: E402
    MemoryKind,
    MemoryRecord,
    Outcome,
    Smriti,
)

CORPUS = "benchmark/incidents"
TENANT = "bench"


class NoAdjacency:
    """The graph knows of no relationships.

    Deliberate for this corpus: with no adjacency, correlation may only group
    findings on the *same* entity. That is the conservative direction the
    Correlation module argues for, and it makes SC-0002 — two unrelated services
    failing in the same minute — a real test rather than one the fixture passes
    by construction.
    """

    def adjacent(self, a: str, b: str, max_depth: int = 3) -> bool:
        return False


def run(scenario: Scenario) -> ScenarioResult:
    events = scenario.events()

    detector = Detector()
    findings = []
    for event in events:
        if event.event_class is EventClass.METRIC:
            findings.extend(detector.process([event]))

    correlator = Correlator(NoAdjacency(), window=timedelta(minutes=5))
    correlation = correlator.correlate(findings)

    merges = measure_merges(correlation.clusters, scenario.truth_for)

    precedent = None
    if scenario.prior_incident:
        memory = Smriti()
        prior = scenario.prior_incident
        memory.remember(
            MemoryRecord(
                id=prior["id"],
                tenant=TENANT,
                kind=MemoryKind.INCIDENT,
                text=prior["text"],
                source="scenario",
                at=events[0].occurred_at - timedelta(days=30),
                entities=frozenset(prior.get("entities", [])),
                signals=frozenset(prior.get("signals", [])),
                outcome=Outcome(
                    resolved=prior.get("resolved", True),
                    diagnosis_correct=prior.get("diagnosis_correct"),
                    action_taken=prior.get("action_taken"),
                ),
            )
        )
        entities = {event.entity_ref.key() for event in events}
        signals = {
            name
            for event in events
            if (name := getattr(event.payload, "name", None)) is not None
        }
        found = memory.precedents(
            TENANT,
            " ".join(sorted(signals)),
            entities=entities,
            signals=signals,
            # Scenario time, not wall-clock. Without this the memory is dated
            # against a fixed epoch while retention is judged against today, so
            # every precedent silently expires and the corpus reports a
            # retrieval failure that is really a clock mismatch.
            now=events[-1].occurred_at,
        )
        precedent = found[0].record.id if found else None

    return ScenarioResult(
        scenario_id=scenario.id,
        expectation=scenario.expectation,
        detected=bool(findings),
        incidents_found=len(correlation.clusters),
        incidents_expected=scenario.expected_incidents,
        incorrect_merges=merges.incorrect_merges,
        incorrect_splits=merges.incorrect_splits,
        precedent_found=precedent,
        precedent_expected=scenario.expected_precedent,
        notes=scenario.notes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--corpus", default=CORPUS)
    args = parser.parse_args()

    scenarios = load_scenarios(args.corpus)
    corpus = CorpusResult(results=[run(scenario) for scenario in scenarios])

    print(f"{'scenario':<10}{'expect':<10}{'detected':<10}{'incidents':<12}{'precedent':<16}verdict")
    print("-" * 76)
    for result in corpus.results:
        verdict = "pass" if result.passed else "FAIL"
        incidents = f"{result.incidents_found}/{result.incidents_expected}"
        precedent = str(result.precedent_found or "—")
        print(
            f"{result.scenario_id:<10}{result.expectation.value:<10}"
            f"{str(result.detected):<10}{incidents:<12}{precedent:<16}{verdict}"
        )

    summary = corpus.summary()
    print("\nFAILURES FIRST")
    print(f"  false alarms      {summary['false_alarms']}   (flagged when the answer was silence)")
    print(f"  missed            {summary['missed']}   (real incident not detected)")
    print(f"  mis-grouped       {summary['mis_grouped']}   (wrong number of incidents)")
    print(f"  false precedents  {summary['false_precedents']}   (claimed history that did not exist)")
    print(f"\n  passed            {summary['passed']}/{summary['total']}")

    print(
        "\nNOT MEASURED HERE: top-1 root-cause accuracy — the Phase 2 exit criterion.\n"
        "It needs a real model; scoring it against the deterministic stub would\n"
        "measure a fixture this repository wrote. Absent rather than reported as a pass.\n"
        "This is telemetry replay, not PIB — do not quote it as a benchmark result."
    )

    if args.strict and (summary["false_alarms"] or summary["mis_grouped"]):
        print("\n::error::a false alarm or incorrect grouping is a blocking failure", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
