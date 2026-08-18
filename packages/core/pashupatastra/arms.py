"""What an arm is allowed to see, and the shared shape every arm implements.

The `Brief` exists because the harness previously handed arms the whole
`PibScenario`, which carries `expected.action` and `expected.root_cause`. An arm
could have scored perfectly by returning the answer key, and every number the
benchmark produced would have been measuring nothing. With two trivial arms that
was harmless; with real arms it is fatal.

So redaction is structural rather than a rule people follow. An arm receives a
Brief and never the scenario, and `test_arms` asserts no field on it carries the
answer — a test that fails the moment someone adds a convenient one.

What an arm sees is what an operator would see: the state of the stack, the
actions it is permitted to take, and the ceiling it works under. Not what was
broken, and not what fixes it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from .pib import PibScenario

# Fields on PibScenario/Expected that an arm must never receive. Named here so
# the guarantee is checkable rather than a matter of reading the constructor.
REDACTED = ("root_cause", "action", "causal_chain", "recovery_state", "escalation_reason", "fault")


@dataclass(frozen=True)
class Brief:
    """One scenario as an arm sees it."""

    scenario_id: str
    stack: str
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    risk_ceiling: int
    observed: dict[str, float] = field(default_factory=dict)
    """Live state read from the stack — the arm's only evidence about what is
    wrong. Deliberately the same dictionary the grader later reads, so an arm
    cannot see more of the world than the benchmark can check."""


def brief_for(scenario: PibScenario, observed: dict[str, float]) -> Brief:
    """Redact a scenario down to what an arm may act on."""
    return Brief(
        scenario_id=scenario.id,
        stack=scenario.stack,
        allowed_actions=scenario.constraints.allowed_actions,
        forbidden_actions=scenario.constraints.forbidden_actions,
        risk_ceiling=scenario.constraints.risk_ceiling,
        observed=dict(observed),
    )


@dataclass(frozen=True)
class Decision:
    """What an arm decided to do. An arm acts or escalates, never both."""

    action: str | None = None
    escalated: bool = False
    rationale: str = ""

    cause: str = ""
    """Why autonomy stopped, as a stable token rather than prose.

    METRICS.md breaks the human-intervention rate down by cause — policy,
    confidence, budget, verification, unrecognised situation — and says the
    breakdown is more informative than the aggregate because it shows *where*
    autonomy stops. Parsing that back out of a rationale string would make the
    metric depend on wording."""

    def __post_init__(self) -> None:
        if self.action and self.escalated:
            raise ValueError(
                "an arm cannot both act and escalate — the grader would have to "
                "decide which one it meant, and either choice invents a result"
            )


class ArmImpl(Protocol):
    """Every arm is the same function of the same evidence.

    The point of the comparison is that only the decision procedure differs. An
    arm that needed extra inputs would not be an arm, it would be a different
    experiment.
    """

    name: str

    def decide(self, brief: Brief) -> Decision: ...


Proposer = Callable[[Brief], str | None]
"""Suggests an action from observed state. Shared between arms on purpose.

Diagnosis quality is not what Phase 5 measures — that needs a real model, and
scoring it against the deterministic stub would measure a fixture this
repository wrote (benchmark/README.md). Holding the proposal constant across
arms isolates the variable that *is* being measured: what the architecture does
with a proposal once it has one.
"""


def unhealthy(brief: Brief) -> bool:
    """Whether the observable state says something is actually wrong."""
    availability = brief.observed.get("availability", 100.0)
    return availability < 100.0 or brief.observed.get("restarts", 0.0) > 0
