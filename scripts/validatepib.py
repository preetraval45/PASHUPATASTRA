"""Validate the PIB corpus and report what it actually covers.

Coverage is printed per category rather than in aggregate. A corpus with a
hundred scenarios and every negative case in one category has negatives on
paper and blind spots in the other seven, and only the per-category view shows
that.

Exits non-zero on a validation failure or a coverage gap, so CI can run it.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "packages/core")

from pashupatastra.pib import (  # noqa: E402
    SEED_CATEGORIES,
    Outcome,
    ScenarioError,
    load_corpus,
    report,
)

CORPUS = sys.argv[1] if len(sys.argv) > 1 else "benchmark/incidents/pib"
MINIMUM = 100

try:
    scenarios = load_corpus(CORPUS)
except ScenarioError as error:
    print(f"INVALID: {error}")
    raise SystemExit(1) from error

result = report(scenarios)
print(f"PIB corpus — {result.total} scenarios in {CORPUS}\n")
print(f"{'category':<12}{'total':>7}{'remediate':>11}{'nothing':>9}{'escalate':>10}")
print("-" * 49)
for category in SEED_CATEGORIES:
    counts = {
        outcome: sum(
            1 for s in scenarios if s.category == category and s.outcome is outcome
        )
        for outcome in Outcome
    }
    print(
        f"{category:<12}{sum(counts.values()):>7}"
        f"{counts[Outcome.REMEDIATE]:>11}{counts[Outcome.NOTHING]:>9}"
        f"{counts[Outcome.ESCALATE]:>10}"
    )
print("-" * 49)
print(
    f"{'all':<12}{result.total:>7}"
    f"{result.by_outcome.get('remediate', 0):>11}"
    f"{result.negatives:>9}{result.escalations:>10}"
)
print(f"\ndifficulty: {result.by_difficulty}")

problems: list[str] = []
if result.total < MINIMUM:
    problems.append(f"only {result.total} scenarios, {MINIMUM} required")
if result.uncovered_categories:
    problems.append(f"categories with no scenarios: {result.uncovered_categories}")
if gap := result.categories_without(Outcome.NOTHING):
    problems.append(f"categories with no negative case: {gap}")
if gap := result.categories_without(Outcome.ESCALATE):
    problems.append(f"categories with no escalation case: {gap}")

if problems:
    print()
    for problem in problems:
        print(f"GAP: {problem}")
    raise SystemExit(1)

print("\nvalid, and every seed category carries a negative and an escalation case")
