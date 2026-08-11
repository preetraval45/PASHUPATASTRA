"""Agent model (v0). See docs/specs/Agent Spec.md.

An agent is a scoped, auditable actor — not a model with shell access. Anything
it can do, it can do because a declaration says so.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .dharma import Environment


class EscalationReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    RISK_EXCEEDS_LIMIT = "risk_exceeds_limit"
    BUDGET_EXHAUSTED = "budget_exhausted"
    VERIFICATION_FAILED = "verification_failed"
    UNRECOGNIZED_SITUATION = "unrecognized_situation"


class Budget(BaseModel):
    """Enforced, not advisory. Exhaustion escalates rather than spends."""

    tokens_per_incident: int = 200_000
    actions_per_incident: int = 5
    wall_clock_seconds: int = 600


class BudgetLedger(BaseModel):
    tokens_used: int = 0
    actions_taken: int = 0
    seconds_elapsed: int = 0

    def exceeded(self, budget: Budget) -> bool:
        return (
            self.tokens_used >= budget.tokens_per_incident
            or self.actions_taken >= budget.actions_per_incident
            or self.seconds_elapsed >= budget.wall_clock_seconds
        )


class AgentSpec(BaseModel):
    name: str
    role: str
    version: int = 1
    environments: list[Environment] = Field(default_factory=lambda: [Environment.DEV])
    permissions: dict[str, bool] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)
    smriti_scope: list[str] = Field(default_factory=list)
    risk_limit: int = Field(default=30, ge=0, le=100)
    budget: Budget = Field(default_factory=Budget)
    goals: list[str] = Field(default_factory=list)

    @property
    def principal(self) -> str:
        return f"agent:{self.name}"

    def may_use(self, tool: str) -> bool:
        """A tool absent from the declaration is unreachable, not discouraged."""
        return tool in self.tools

    def authorized_in(self, environment: Environment) -> bool:
        """Environment promotion is explicit — staging proof grants no prod authority."""
        return environment in self.environments


def load_agent_spec(path: str | Path) -> AgentSpec:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    agent = data.get("agent", data)
    flat = {
        **agent,
        **{k: v for k, v in data.items() if k != "agent"},
    }
    identity = flat.pop("identity", {}) or {}
    memory = flat.pop("memory", {}) or {}
    approval = flat.pop("approval", {}) or {}
    flat.setdefault("environments", identity.get("environments", ["dev"]))
    flat.setdefault("smriti_scope", memory.get("smriti_scope", []))
    if "required_above" in approval:
        flat.setdefault("risk_limit", approval["required_above"])
    return AgentSpec.model_validate(flat)
