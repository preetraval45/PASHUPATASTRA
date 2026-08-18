"""The agent runtime — what turns an `AgentSpec` from a document into a cage.

`AgentSpec` already declares what an agent may use, where it may run, and what it
may spend. That is a *description* until something enforces it. This module is
that something, and every guarantee in `docs/specs/Agent Spec.md` is either made
true here or is not true at all.

Four properties, each chosen against a specific way this goes wrong:

**The allow-list is checked at call time, never at load time.** A runtime that
validates the tool set once and then trusts itself is one refactor away from a
tool acquired mid-run being callable. Checking on every call costs a dictionary
lookup and removes the whole class of bug.

**Budgets are checked before the spend, not after.** Enforced afterwards, a
budget is a report. The agent is stopped *before* the call that would exceed it,
which means the ceiling is a ceiling rather than a description of where it
stopped.

**Exhaustion escalates. It does not fail silently and it does not continue.**
A runaway loop that quietly stops looks identical to a task that finished, and
the incident sits untouched while everyone believes an agent has it.

**The risk ceiling is enforced above approval.** An agent with limit 40 cannot
execute a risk-45 action *even with a human approving it*. Approval answers "may
this be done"; the ceiling answers "may this actor do it", and collapsing the two
would let an agent escalate its own authority by asking nicely.

Escalation is a **success outcome** throughout, not an error path. The benchmark
measures false remediation precisely so that guessing is never rewarded over
handing off, and a runtime that treated escalation as failure would create
pressure in exactly the wrong direction.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .agents import AgentSpec, Budget, BudgetLedger, EscalationReason
from .dharma import Environment, RiskContext, Verdict, evaluate
from .registry import get as get_action


class ToolDenied(Exception):
    """A tool the declaration does not grant. Raised, never returned.

    An exception rather than an error result on purpose: a denied tool is a
    programming or prompt failure, and a caller that can accidentally ignore a
    return value is a caller that will.
    """


@dataclass
class ToolCall:
    """One attempt to use a tool, allowed or not.

    Denied calls are recorded too. An agent repeatedly reaching for something it
    cannot have is a signal — either its declaration is too narrow for its job or
    its prompt is wrong — and discarding those attempts hides it.
    """

    name: str
    args: dict[str, Any]
    at: datetime
    allowed: bool
    result: str | None = None
    error: str | None = None


@dataclass
class Escalation:
    """A hand-off to a human, with why."""

    reason: EscalationReason
    detail: str
    at: datetime

    def describe(self) -> str:
        return f"{self.reason.value}: {self.detail}"


@dataclass
class AgentRun:
    """Everything one agent did, including what it was refused."""

    agent: str
    incident_id: str | None
    started_at: datetime
    ledger: BudgetLedger = field(default_factory=BudgetLedger)
    calls: list[ToolCall] = field(default_factory=list)
    escalation: Escalation | None = None

    @property
    def escalated(self) -> bool:
        return self.escalation is not None

    @property
    def denied_calls(self) -> list[ToolCall]:
        return [call for call in self.calls if not call.allowed]

    def summary(self) -> dict[str, object]:
        return {
            "agent": self.agent,
            "incident": self.incident_id,
            "tool_calls": len(self.calls),
            "denied_calls": len(self.denied_calls),
            "tokens_used": self.ledger.tokens_used,
            "actions_taken": self.ledger.actions_taken,
            "seconds_elapsed": self.ledger.seconds_elapsed,
            "escalated": self.escalated,
            "escalation": self.escalation.describe() if self.escalation else None,
        }


class AgentRuntime:
    """Runs one agent inside its declaration.

    Deliberately not an orchestrator and not a loop: it is the boundary an agent
    acts through. What the agent decides to do is the reasoning layer's problem;
    what it is *permitted* to do is this one's, and keeping those separate is
    what makes the permission side auditable on its own.
    """

    def __init__(
        self,
        spec: AgentSpec,
        tools: dict[str, Callable[..., str]],
        environment: Environment,
        incident_id: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.spec = spec
        self.environment = environment
        self._now = clock or (lambda: datetime.now().astimezone())
        self.run = AgentRun(
            agent=spec.name, incident_id=incident_id, started_at=self._now()
        )

        # Tools present in the registry but absent from the declaration are
        # dropped at construction *as well as* being refused at call time. Belt
        # and braces: the call-time check is the guarantee, and not holding an
        # undeclared callable at all means a bug cannot reach one.
        self._tools = {name: fn for name, fn in tools.items() if spec.may_use(name)}
        self._undeclared = sorted(set(tools) - set(self._tools))

    # -- authorization --------------------------------------------------------

    def authorized(self) -> bool:
        """Whether this agent may run here at all.

        Environment promotion is explicit: proof in staging grants no production
        authority (`docs/specs/Agent Spec.md`, guarantee 4).
        """
        return self.spec.authorized_in(self.environment)

    # -- tools ----------------------------------------------------------------

    def call(self, tool: str, **args: Any) -> str:
        """Use a tool, or refuse.

        The allow-list is consulted here, on every call — not once at startup.
        """
        now = self._now()

        if not self.spec.may_use(tool):
            self.run.calls.append(
                ToolCall(name=tool, args=args, at=now, allowed=False,
                         error="not declared in this agent's tools")
            )
            raise ToolDenied(
                f"{self.spec.name} may not use {tool!r}; declared tools are "
                f"{', '.join(sorted(self.spec.tools)) or '(none)'}"
            )

        if (exhausted := self._exhausted(now)) is not None:
            self.run.calls.append(
                ToolCall(name=tool, args=args, at=now, allowed=False, error=exhausted.detail)
            )
            self._escalate(exhausted.reason, exhausted.detail, now)
            raise ToolDenied(exhausted.detail)

        call = ToolCall(name=tool, args=args, at=now, allowed=True)
        self.run.calls.append(call)
        try:
            call.result = self._tools[tool](**args)
        except Exception as error:  # noqa: BLE001 — recorded, then re-raised
            call.error = f"{type(error).__name__}: {error}"
            raise
        return call.result

    def available_tools(self) -> list[str]:
        """What this agent can actually call.

        Derived from the declaration, so a prompt built from this cannot offer
        the model a tool the runtime would then refuse — which would look to the
        model like the system malfunctioning rather than like a boundary.
        """
        return sorted(self._tools)

    # -- acting ---------------------------------------------------------------

    def authorize(
        self,
        action_id: str,
        context: RiskContext,
    ) -> Verdict:
        """Ask Dharma whether this agent may perform this action.

        The agent's `risk_limit` is passed as the ceiling, so the answer accounts
        for *who is asking* and not only for what is being asked. There is no
        path here that produces a verdict without it.
        """
        return evaluate(
            action=get_action(action_id),
            context=context,
            incident_ref=self.run.incident_id,
            agent_risk_limit=self.spec.risk_limit,
        )

    def record_action(self) -> None:
        """Count an executed action against the budget.

        Separate from `authorize` because a verdict is not an execution: an agent
        that asked and was refused has not spent an action, and charging it would
        make the budget punish caution.
        """
        self.run.ledger.actions_taken += 1

    def record_tokens(self, tokens: int) -> None:
        self.run.ledger.tokens_used += tokens

    # -- budget ---------------------------------------------------------------

    def _exhausted(self, now: datetime) -> Escalation | None:
        """Whether the next call would exceed the declaration. Checked *before*."""
        budget: Budget = self.spec.budget
        elapsed = int((now - self.run.started_at).total_seconds())
        self.run.ledger.seconds_elapsed = elapsed

        if self.run.ledger.tokens_used >= budget.tokens_per_incident:
            return Escalation(
                EscalationReason.BUDGET_EXHAUSTED,
                f"token budget spent ({self.run.ledger.tokens_used}/"
                f"{budget.tokens_per_incident})",
                now,
            )
        if self.run.ledger.actions_taken >= budget.actions_per_incident:
            return Escalation(
                EscalationReason.BUDGET_EXHAUSTED,
                f"action budget spent ({self.run.ledger.actions_taken}/"
                f"{budget.actions_per_incident})",
                now,
            )
        if elapsed >= budget.wall_clock_seconds:
            return Escalation(
                EscalationReason.BUDGET_EXHAUSTED,
                f"wall clock exceeded ({elapsed}s/{budget.wall_clock_seconds}s)",
                now,
            )
        return None

    # -- escalation -----------------------------------------------------------

    def escalate(self, reason: EscalationReason, detail: str) -> Escalation:
        """Hand off to a human. A success outcome, not a failure."""
        return self._escalate(reason, detail, self._now())

    def _escalate(
        self, reason: EscalationReason, detail: str, now: datetime
    ) -> Escalation:
        # First escalation wins. A later one would overwrite the reason the agent
        # actually stopped for, and the first reason is the true one — everything
        # after it is a consequence.
        if self.run.escalation is None:
            self.run.escalation = Escalation(reason=reason, detail=detail, at=now)
        return self.run.escalation


# --- the fleet ----------------------------------------------------------------


def sati_roles() -> dict[str, AgentSpec]:
    """Sati's first roles — one identity, specialised, not four products.

    Each is deliberately narrow. An agent that can do everything has the blast
    radius of everything, and the least-privilege guarantee is only meaningful if
    the declarations actually differ.

    Risk ceilings are set below the tier they would need for their most dangerous
    plausible action, so escalation is the *normal* path for anything consequential
    rather than an exception. That is intentional: the fleet should feel slightly
    too cautious at first, because the cost of loosening it later is a config
    change and the cost of tightening it is an incident.
    """
    return {
        "sati.orchestrator": AgentSpec(
            name="sati.orchestrator",
            role="Route work to the right role and combine what they report",
            environments=[Environment.DEV],
            tools=["smriti.retrieve", "topology.blast_radius"],
            risk_limit=0,
            # Deliberately zero: the orchestrator decides *who* acts, never acts
            # itself. An orchestrator that can act accumulates the union of every
            # role's authority without ever declaring it.
        ),
        "sati.incident": AgentSpec(
            name="sati.incident",
            role="Diagnose an incident and propose a remediation",
            environments=[Environment.DEV],
            tools=[
                "prometheus.query",
                "opensearch.search",
                "topology.blast_radius",
                "smriti.retrieve",
                "astra.restart_service",
            ],
            risk_limit=30,
            budget=Budget(tokens_per_incident=200_000, actions_per_incident=3),
        ),
        "sati.infrastructure": AgentSpec(
            name="sati.infrastructure",
            role="Act on infrastructure once a diagnosis is established",
            environments=[Environment.DEV],
            tools=[
                "prometheus.query",
                "topology.blast_radius",
                "astra.restart_service",
                "astra.scale_service",
                "astra.rollback_deployment",
            ],
            risk_limit=45,
            budget=Budget(tokens_per_incident=100_000, actions_per_incident=5),
        ),
        "sati.security": AgentSpec(
            name="sati.security",
            role="Investigate security-relevant signals. Read-only.",
            environments=[Environment.DEV],
            tools=["opensearch.search", "cloudtrail.lookup", "smriti.retrieve"],
            risk_limit=0,
            # Read-only by declaration, not by convention. A security agent that
            # can act is the one an attacker most wants to reach, and Kavach
            # (Phases 7-12) widens this surface considerably — starting it at
            # zero means every later grant is a visible, argued diff.
            budget=Budget(tokens_per_incident=200_000, actions_per_incident=0),
        ),
    }
