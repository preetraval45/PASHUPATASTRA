"""PIB — the Pashupatastra Incident Benchmark: schema and validator.

Separate from `scenarios.py` on purpose. That module replays telemetry from YAML
to measure the Phase 2 loop; PIB injects faults into a running stack and scores
the whole loop across four arms. Collapsing them into one type would blur the
distinction benchmark/README.md spends a table making, and the Phase 2 corpus
would start looking like benchmark results.

The validator carries most of the weight here. A corpus of a hundred
hand-authored files accumulates mistakes that are invisible one file at a time —
an expected action absent from its own allow-list, a negative case that quietly
expects a remediation — and each one silently changes what the benchmark
measures. Every rule below exists because it makes a specific authoring error
impossible to commit rather than merely discouraged.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

SEED_CATEGORIES = (
    "database",
    "cache",
    "compute",
    "deployment",
    "dependency",
    "network",
    "queue",
    "security",
)


class Outcome(StrEnum):
    """What the correct answer is. The benchmark's whole point is that these are
    three different right answers, not one right answer and two failures."""

    REMEDIATE = "remediate"
    NOTHING = "nothing"
    """Benign activity that resembles a problem. Silence is the correct answer,
    and a system that cannot stay silent is not deployable."""

    ESCALATE = "escalate"
    """Real, and not something the system should resolve alone. Handing off is a
    success outcome; a benchmark that scores it as failure teaches guessing."""


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class Fault:
    """What is done to the stack to create the scenario."""

    type: str
    detail: str
    target: str | None = None


@dataclass(frozen=True)
class Expected:
    """The answer key, authored before the logic that resolves it."""

    root_cause: str | None = None
    causal_chain: tuple[str, ...] = ()
    action: str | None = None
    recovery_state: dict[str, str] = field(default_factory=dict)
    escalation_reason: str | None = None


@dataclass(frozen=True)
class Constraints:
    allowed_actions: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    risk_ceiling: int = 100


@dataclass(frozen=True)
class PibScenario:
    id: str
    name: str
    category: str
    difficulty: Difficulty
    outcome: Outcome
    stack: str
    fault: Fault
    expected: Expected
    constraints: Constraints
    notes: str = ""

    @property
    def is_negative(self) -> bool:
        return self.outcome is Outcome.NOTHING


class ScenarioError(ValueError):
    """A scenario that would silently change what the benchmark measures."""


def _require(data: dict[str, Any], key: str, where: str) -> Any:
    if key not in data:
        raise ScenarioError(f"{where}: missing required field {key!r}")
    return data[key]


def load_scenario(data: dict[str, Any], source: str = "<dict>") -> PibScenario:
    """Parse and validate one scenario. Raises rather than warning.

    A warning on a corpus this size is a line of output nobody reads, and the
    scenario still runs — scoring something other than what it claims to score.
    """
    scenario = _require(data, "scenario", source)
    sid = _require(scenario, "id", source)
    where = f"{source} ({sid})"

    category = _require(scenario, "category", where)
    if category not in SEED_CATEGORIES:
        raise ScenarioError(
            f"{where}: category {category!r} is not one of the eight seed "
            f"categories {SEED_CATEGORIES}"
        )

    try:
        outcome = Outcome(_require(scenario, "outcome", where))
        difficulty = Difficulty(scenario.get("difficulty", "medium"))
    except ValueError as exc:
        raise ScenarioError(f"{where}: {exc}") from exc

    setup = _require(data, "setup", where)
    fault_raw = _require(setup, "fault", where)
    fault = Fault(
        type=_require(fault_raw, "type", where),
        detail=_require(fault_raw, "detail", where),
        target=fault_raw.get("target"),
    )

    expected_raw = data.get("expected") or {}
    expected = Expected(
        root_cause=expected_raw.get("root_cause"),
        causal_chain=tuple(expected_raw.get("causal_chain") or ()),
        action=expected_raw.get("action"),
        recovery_state=dict(expected_raw.get("recovery_state") or {}),
        escalation_reason=expected_raw.get("escalation_reason"),
    )

    constraints_raw = data.get("constraints") or {}
    constraints = Constraints(
        allowed_actions=tuple(constraints_raw.get("allowed_actions") or ()),
        forbidden_actions=tuple(constraints_raw.get("forbidden_actions") or ()),
        risk_ceiling=int(constraints_raw.get("risk_ceiling", 100)),
    )

    built = PibScenario(
        id=sid,
        name=_require(scenario, "name", where),
        category=category,
        difficulty=difficulty,
        outcome=outcome,
        stack=_require(setup, "stack", where),
        fault=fault,
        expected=expected,
        constraints=constraints,
        notes=scenario.get("notes", ""),
    )
    _check(built, where)
    return built


def _check(s: PibScenario, where: str) -> None:
    """The rules that make a mis-authored scenario impossible to commit."""
    overlap = set(s.constraints.allowed_actions) & set(s.constraints.forbidden_actions)
    if overlap:
        raise ScenarioError(
            f"{where}: {sorted(overlap)} is both allowed and forbidden — the grader "
            "would count the same action as correct and as a false remediation"
        )

    if not 0 <= s.constraints.risk_ceiling <= 100:
        raise ScenarioError(f"{where}: risk_ceiling {s.constraints.risk_ceiling} is outside 0–100")

    if s.outcome is Outcome.REMEDIATE:
        if not s.expected.root_cause:
            raise ScenarioError(f"{where}: a remediate scenario must state its root cause")
        if not s.expected.action:
            raise ScenarioError(f"{where}: a remediate scenario must state the correct action")
        if not s.expected.recovery_state:
            raise ScenarioError(
                f"{where}: a remediate scenario must state its recovery state, or "
                "'did it work?' has no answer and the run is unscoreable"
            )
        if s.expected.action not in s.constraints.allowed_actions:
            raise ScenarioError(
                f"{where}: expected action {s.expected.action!r} is not in its own "
                f"allowed_actions {list(s.constraints.allowed_actions)} — the answer "
                "key and the constraint contradict each other"
            )
        if s.expected.action in s.constraints.forbidden_actions:
            raise ScenarioError(
                f"{where}: expected action {s.expected.action!r} is forbidden by the "
                "same scenario"
            )

    # The two rules the negative and escalation cases exist for. A negative case
    # carrying an expected action is not a negative case, and it would score a
    # system that acted as correct — rewarding exactly the behaviour the category
    # was added to penalise.
    if s.outcome is Outcome.NOTHING:
        if s.expected.action:
            raise ScenarioError(
                f"{where}: a negative scenario cannot expect an action — the correct "
                "answer is silence"
            )
        if s.expected.root_cause:
            raise ScenarioError(
                f"{where}: a negative scenario has no root cause; benign activity is "
                "not a fault with a cause to find"
            )

    if s.outcome is Outcome.ESCALATE:
        if s.expected.action:
            raise ScenarioError(
                f"{where}: an escalation scenario cannot expect a remediation — "
                "handing off is the correct answer"
            )
        if not s.expected.escalation_reason:
            raise ScenarioError(
                f"{where}: an escalation scenario must say why it escalates, or the "
                "grader cannot tell a correct hand-off from a system that gave up"
            )


def load_corpus(directory: str | Path) -> list[PibScenario]:
    """Load every scenario in a directory, failing on the first bad one."""
    path = Path(directory)
    scenarios: list[PibScenario] = []
    for file in sorted(path.glob("*.yaml")):
        with file.open(encoding="utf-8-sig") as handle:
            scenarios.append(load_scenario(yaml.safe_load(handle), file.name))

    duplicates = _duplicates(s.id for s in scenarios)
    if duplicates:
        raise ScenarioError(f"duplicate scenario ids: {sorted(duplicates)}")
    return scenarios


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    return {v for v in values if v in seen or seen.add(v)}  # type: ignore[func-returns-value]


@dataclass
class CorpusReport:
    """What the corpus actually covers, rather than what it claims to."""

    total: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_outcome: dict[str, int] = field(default_factory=dict)
    by_difficulty: dict[str, int] = field(default_factory=dict)

    @property
    def negatives(self) -> int:
        return self.by_outcome.get(Outcome.NOTHING.value, 0)

    @property
    def escalations(self) -> int:
        return self.by_outcome.get(Outcome.ESCALATE.value, 0)

    @property
    def uncovered_categories(self) -> list[str]:
        return [c for c in SEED_CATEGORIES if not self.by_category.get(c)]

    def categories_without(self, outcome: Outcome) -> list[str]:
        """Named per category, because a corpus with negatives only in `network`
        has negatives in aggregate and blind spots everywhere else."""
        return [c for c in SEED_CATEGORIES if not self._count(c, outcome)]

    def _count(self, category: str, outcome: Outcome) -> int:
        return self._pairs.get((category, outcome.value), 0)

    _pairs: dict[tuple[str, str], int] = field(default_factory=dict)

    def summary(self) -> dict[str, object]:
        return {
            "total": self.total,
            "by_category": dict(sorted(self.by_category.items())),
            "by_outcome": dict(sorted(self.by_outcome.items())),
            "by_difficulty": dict(sorted(self.by_difficulty.items())),
            "negatives": self.negatives,
            "escalations": self.escalations,
            "uncovered_categories": self.uncovered_categories,
            "categories_without_negatives": self.categories_without(Outcome.NOTHING),
            "categories_without_escalations": self.categories_without(Outcome.ESCALATE),
        }


def report(scenarios: list[PibScenario]) -> CorpusReport:
    result = CorpusReport(total=len(scenarios))
    for s in scenarios:
        result.by_category[s.category] = result.by_category.get(s.category, 0) + 1
        result.by_outcome[s.outcome.value] = result.by_outcome.get(s.outcome.value, 0) + 1
        result.by_difficulty[s.difficulty.value] = (
            result.by_difficulty.get(s.difficulty.value, 0) + 1
        )
        key = (s.category, s.outcome.value)
        result._pairs[key] = result._pairs.get(key, 0) + 1
    return result
