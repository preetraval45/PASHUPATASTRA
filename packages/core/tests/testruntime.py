"""The agent runtime — where the declaration becomes a cage.

`AgentSpec` describes limits; these tests are the evidence the limits hold. The
weight is on refusal: an agent doing what it is allowed to do is the easy half,
and every guarantee in the spec is about what happens when it tries not to.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pashupatastra.agents import AgentSpec, Budget, EscalationReason
from pashupatastra.dharma import Environment, RiskContext, Tier
from pashupatastra.runtime import (
    AgentRuntime,
    ToolDenied,
    sati_roles,
)

NOW = datetime(2026, 8, 18, 10, 0, 0).astimezone()


def a_spec(**overrides) -> AgentSpec:
    defaults = {
        "name": "sati.test",
        "role": "test",
        "environments": [Environment.DEV],
        "tools": ["prometheus.query"],
        "risk_limit": 30,
        "budget": Budget(tokens_per_incident=1000, actions_per_incident=2,
                         wall_clock_seconds=600),
    }
    return AgentSpec(**{**defaults, **overrides})


def a_runtime(spec: AgentSpec | None = None, clock=None, **tools) -> AgentRuntime:
    return AgentRuntime(
        spec=spec or a_spec(),
        tools=tools or {"prometheus.query": lambda **_: "42"},
        environment=Environment.DEV,
        incident_id="INC-1",
        clock=clock or (lambda: NOW),
    )


# --- the allow-list, checked at call time ------------------------------------


def test_a_declared_tool_can_be_called() -> None:
    runtime = a_runtime(**{"prometheus.query": lambda query="": f"result:{query}"})
    assert runtime.call("prometheus.query", query="up") == "result:up"


def test_an_undeclared_tool_is_unreachable() -> None:
    runtime = a_runtime()
    with pytest.raises(ToolDenied, match="may not use"):
        runtime.call("astra.delete_infrastructure")


def test_the_allow_list_is_consulted_on_every_call_not_once_at_startup() -> None:
    """A runtime that validates once and then trusts itself is one refactor away
    from a tool acquired mid-run being callable."""
    runtime = a_runtime()
    runtime.call("prometheus.query")

    # Mutate the declaration after construction, as a bug or a compromise would.
    runtime.spec.tools.remove("prometheus.query")
    with pytest.raises(ToolDenied):
        runtime.call("prometheus.query")


def test_an_undeclared_callable_is_never_even_held() -> None:
    """Belt and braces: the call-time check is the guarantee, but not holding the
    callable means a bug cannot reach one."""
    runtime = a_runtime(
        **{"prometheus.query": lambda **_: "ok", "astra.delete_infrastructure": lambda **_: "boom"}
    )
    assert runtime.available_tools() == ["prometheus.query"]
    assert "astra.delete_infrastructure" not in runtime._tools


def test_denied_calls_are_recorded_not_discarded() -> None:
    """An agent repeatedly reaching for something it cannot have is a signal —
    either its declaration is too narrow or its prompt is wrong."""
    runtime = a_runtime()
    for _ in range(3):
        with pytest.raises(ToolDenied):
            runtime.call("astra.scale_service")

    assert len(runtime.run.denied_calls) == 3
    assert runtime.run.summary()["denied_calls"] == 3


def test_available_tools_matches_what_the_runtime_will_allow() -> None:
    """A prompt built from this cannot offer the model a tool the runtime would
    then refuse — which would read as a malfunction rather than a boundary."""
    runtime = a_runtime()
    for tool in runtime.available_tools():
        runtime.call(tool)


# --- environment authorization -----------------------------------------------


def test_an_agent_proven_in_staging_has_no_production_authority() -> None:
    """Environment promotion is explicit (Agent Spec, guarantee 4)."""
    runtime = AgentRuntime(
        spec=a_spec(environments=[Environment.STAGING]),
        tools={},
        environment=Environment.PROD,
        clock=lambda: NOW,
    )
    assert not runtime.authorized()


def test_an_agent_is_authorized_where_it_is_declared() -> None:
    assert a_runtime().authorized()


# --- budgets, checked before the spend ---------------------------------------


def test_the_action_budget_stops_the_call_that_would_exceed_it() -> None:
    """Enforced afterwards, a budget is a report."""
    runtime = a_runtime(spec=a_spec(budget=Budget(actions_per_incident=2)))
    runtime.record_action()
    runtime.record_action()

    with pytest.raises(ToolDenied, match="action budget"):
        runtime.call("prometheus.query")


def test_the_token_budget_is_enforced() -> None:
    runtime = a_runtime(spec=a_spec(budget=Budget(tokens_per_incident=100)))
    runtime.record_tokens(100)

    with pytest.raises(ToolDenied, match="token budget"):
        runtime.call("prometheus.query")


def test_the_wall_clock_is_enforced() -> None:
    """A runaway loop that is cheap per call still runs forever."""
    times = iter([NOW, NOW + timedelta(seconds=700)])
    runtime = a_runtime(
        spec=a_spec(budget=Budget(wall_clock_seconds=600)), clock=lambda: next(times)
    )
    with pytest.raises(ToolDenied, match="wall clock"):
        runtime.call("prometheus.query")


def test_exhaustion_escalates_rather_than_failing_silently() -> None:
    """A runaway loop that quietly stops looks identical to a task that finished,
    and the incident sits untouched while everyone believes an agent has it."""
    runtime = a_runtime(spec=a_spec(budget=Budget(actions_per_incident=1)))
    runtime.record_action()

    with pytest.raises(ToolDenied):
        runtime.call("prometheus.query")

    assert runtime.run.escalated
    assert runtime.run.escalation.reason is EscalationReason.BUDGET_EXHAUSTED


def test_a_refused_action_does_not_spend_the_action_budget() -> None:
    """Charging for a refusal would make the budget punish caution."""
    runtime = a_runtime()
    runtime.authorize("restart_service", RiskContext(environment=Environment.DEV))
    assert runtime.run.ledger.actions_taken == 0


# --- the risk ceiling, enforced above approval -------------------------------


def test_the_agent_risk_ceiling_is_passed_to_the_policy_engine() -> None:
    """The verdict must account for *who* is asking, not only what is asked."""
    runtime = a_runtime(spec=a_spec(risk_limit=10))
    verdict = runtime.authorize(
        "rollback_deployment", RiskContext(environment=Environment.DEV)
    )
    assert verdict.tier is Tier.DENIED, "risk 45 action, agent ceiling 10"


def test_an_agent_within_its_ceiling_is_permitted() -> None:
    runtime = a_runtime(spec=a_spec(risk_limit=45))
    verdict = runtime.authorize(
        "restart_service", RiskContext(environment=Environment.DEV)
    )
    assert verdict.tier is not Tier.DENIED


def test_a_human_cannot_approve_past_an_agents_ceiling() -> None:
    """Approval answers "may this be done"; the ceiling answers "may this actor
    do it". Collapsing them lets an agent escalate its own authority by asking."""
    runtime = a_runtime(spec=a_spec(risk_limit=10))
    verdict = runtime.authorize(
        "rollback_deployment", RiskContext(environment=Environment.DEV)
    )
    verdict.granted_by = "human:alice"
    assert not verdict.is_executable, "a granted verdict above the ceiling is still dead"


# --- escalation ---------------------------------------------------------------


def test_escalation_records_a_reason() -> None:
    runtime = a_runtime()
    escalation = runtime.escalate(
        EscalationReason.LOW_CONFIDENCE, "no hypothesis cleared 0.4"
    )
    assert escalation.reason is EscalationReason.LOW_CONFIDENCE
    assert "0.4" in runtime.run.escalation.detail


def test_the_first_escalation_reason_wins() -> None:
    """The first reason is the true one; everything after it is a consequence."""
    runtime = a_runtime()
    runtime.escalate(EscalationReason.LOW_CONFIDENCE, "first")
    runtime.escalate(EscalationReason.BUDGET_EXHAUSTED, "second")
    assert runtime.run.escalation.detail == "first"


def test_escalation_is_visible_in_the_run_summary() -> None:
    runtime = a_runtime()
    runtime.escalate(EscalationReason.UNRECOGNIZED_SITUATION, "never seen this")
    summary = runtime.run.summary()
    assert summary["escalated"] is True
    assert "unrecognized_situation" in summary["escalation"]


# --- the fleet ----------------------------------------------------------------


def test_the_orchestrator_cannot_act() -> None:
    """An orchestrator that can act accumulates the union of every role's
    authority without ever declaring it."""
    orchestrator = sati_roles()["sati.orchestrator"]
    assert orchestrator.risk_limit == 0
    assert not any(tool.startswith("astra.") for tool in orchestrator.tools)


def test_the_security_role_is_read_only_by_declaration() -> None:
    """Not by convention. A security agent that can act is the one an attacker
    most wants to reach."""
    security = sati_roles()["sati.security"]
    assert security.risk_limit == 0
    assert security.budget.actions_per_incident == 0
    assert not any(tool.startswith("astra.") for tool in security.tools)


def test_the_roles_have_genuinely_different_declarations() -> None:
    """Least privilege is only meaningful if the declarations actually differ —
    four identical specs would satisfy the model and none of its intent."""
    roles = sati_roles()
    toolsets = {name: frozenset(spec.tools) for name, spec in roles.items()}
    assert len(set(toolsets.values())) == len(roles), "two roles share a tool set"
    assert len({spec.risk_limit for spec in roles.values()}) > 1


def test_no_role_can_reach_an_irreversible_action() -> None:
    """`delete_infrastructure` is registered so policy can deny it. No role should
    be able to name it at all."""
    for spec in sati_roles().values():
        assert not any("delete" in tool for tool in spec.tools)


def test_every_role_is_dev_only_for_now() -> None:
    """Promotion is explicit and has not happened. If this test starts failing,
    someone widened production authority — which should be a visible diff."""
    for name, spec in sati_roles().items():
        assert spec.environments == [Environment.DEV], f"{name} escaped dev"


def test_a_role_can_only_use_what_it_declares() -> None:
    """The fleet wired through the real runtime, not just inspected."""
    incident = sati_roles()["sati.incident"]
    runtime = AgentRuntime(
        spec=incident,
        tools={
            "prometheus.query": lambda **_: "ok",
            "astra.rollback_deployment": lambda **_: "rolled back",
        },
        environment=Environment.DEV,
        clock=lambda: NOW,
    )
    assert runtime.call("prometheus.query") == "ok"
    with pytest.raises(ToolDenied):
        # Declared for sati.infrastructure, not for sati.incident.
        runtime.call("astra.rollback_deployment")
