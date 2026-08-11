"""Agent declaration loading and enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from pashupatastra import Budget, BudgetLedger, Environment, load_agent_spec

SPEC = Path(__file__).resolve().parents[3] / "services/api/app/policies/databaseresponder.yaml"


@pytest.fixture
def agent():
    return load_agent_spec(SPEC)


def test_declaration_loads(agent) -> None:
    assert agent.name == "database-responder"
    assert agent.principal == "agent:database-responder"
    assert agent.risk_limit == 40


def test_undeclared_tool_is_unreachable(agent) -> None:
    assert agent.may_use("astra.restart_service")
    assert not agent.may_use("astra.modify_db_config")
    assert not agent.may_use("shell.exec")


def test_environment_promotion_is_explicit(agent) -> None:
    assert agent.authorized_in(Environment.STAGING)
    assert not agent.authorized_in(Environment.PROD), "staging proof grants no prod authority"


def test_risk_limit_blocks_actions_above_ceiling(agent) -> None:
    from pashupatastra import Tier, evaluate
    from pashupatastra.registry import get

    verdict = evaluate(
        get("rollback_deployment"),
        __import__("pashupatastra").RiskContext(environment=Environment.STAGING),
        agent_risk_limit=agent.risk_limit,
    )
    assert verdict.tier is Tier.DENIED


def test_budget_exhaustion_is_detected() -> None:
    budget = Budget(tokens_per_incident=1000, actions_per_incident=2, wall_clock_seconds=60)
    ledger = BudgetLedger()
    assert not ledger.exceeded(budget)

    ledger.actions_taken = 2
    assert ledger.exceeded(budget), "budgets are enforced, not advisory"
