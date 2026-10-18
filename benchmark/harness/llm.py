"""The LLM proposer for the baseline arms (RP-07, adr/LLMBaselines).

An LLM replaces exactly one thing — the proposal — and nothing after it, so the
2 × 2 isolates the proposer from the architecture. It sees the same `Brief` as
every other arm (never the scenario's expected answer), answers through the AI
Gateway with a validated `proposal_v1`, and may only name an allowed action,
`do_nothing`, or `escalate`.

Failures are kept apart from wrong answers: a provider or schema failure comes
back as `llm_error`, an action that was not on the list as `off_list`. Both
are safe outcomes (nothing runs), and both are counted separately so a table can
tell "chose badly" from "could not answer".
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pashupatastra.arms import Brief
from pashupatastra.gateway import (
    CircuitBreaker,
    Evidence,
    Gateway,
    GatewayError,
    ModelRequest,
)

DO_NOTHING = "do_nothing"
ESCALATE = "escalate"

INSTRUCTIONS = """You are the proposer in an incident-response benchmark. You \
are given the live, observed state of one service and the actions you are \
allowed to take. Decide the single best next step:
- one of the allowed action ids, exactly as written;
- "do_nothing" if the observed state shows nothing is wrong;
- "escalate" if a human should decide (for example the right action is not allowed, \
or the risk is too high).
Return JSON matching the schema. Choose only from the allowed ids."""

QUESTION = "Given the brief (evidence ref 'brief'), what is the single best next step?"


@dataclass(frozen=True)
class Proposal:
    action: str | None
    """An allowed action id, or None for do-nothing."""
    escalate: bool = False
    cause: str = ""
    """'' for a valid answer; 'llm_error' or 'off_list' otherwise."""
    reason: str = ""


def render(brief: Brief) -> str:
    observed = "\n".join(f"  {k}: {v}" for k, v in sorted(brief.observed.items())) or "  (nothing observed)"
    return (
        f"stack: {brief.stack}\n"
        f"observed state:\n{observed}\n"
        f"allowed actions: {', '.join(brief.allowed_actions) or '(none)'}\n"
        f"forbidden actions: {', '.join(brief.forbidden_actions) or '(none)'}\n"
        f"risk ceiling: {brief.risk_ceiling}"
    )


class LLMProposer:
    def __init__(self, gateway: Gateway) -> None:
        self.gateway = gateway

    @property
    def model(self) -> str:
        return getattr(self.gateway.provider, "model", "")

    def propose(self, brief: Brief) -> Proposal:
        try:
            response = self.gateway.complete(
                ModelRequest(
                    purpose="baseline_proposal",
                    instructions=INSTRUCTIONS,
                    question=QUESTION,
                    schema_name="proposal_v1",
                    # Platform-authored: the harness wrote this from live state.
                    evidence=[Evidence(ref="brief", source="harness", content=render(brief), trusted=True)],
                    incident_id=brief.scenario_id,
                    agent="baseline",
                    max_tokens=200,
                )
            )
        except GatewayError as error:
            return Proposal(action=None, escalate=True, cause="llm_error", reason=str(error)[:200])

        action = str(response.output.get("action", "")).strip()
        reason = str(response.output.get("reason", ""))[:200]
        if action == DO_NOTHING:
            return Proposal(action=None, reason=reason)
        if action == ESCALATE:
            return Proposal(action=None, escalate=True, cause="model_escalated", reason=reason)
        if action not in brief.allowed_actions:
            return Proposal(action=None, escalate=True, cause="off_list", reason=f"proposed {action!r}")
        return Proposal(action=action, reason=reason)


def baseline_gateway(model: str) -> Gateway:
    """A gateway to the self-hosted baseline endpoint (Ollama), from the
    environment: `PASHU_BASELINE_BASE_URL`, key in `PASHU_BASELINE_API_KEY`,
    temperature `PASHU_BASELINE_TEMPERATURE` (default 0.2, adr/LLMBaselines).

    Refuses to build without an endpoint — there is no stub fallback, because
    an LLM baseline answered by a fixture would be fabricated.
    """
    base_url = os.environ.get("PASHU_BASELINE_BASE_URL", "")
    if not base_url:
        raise RuntimeError(
            "PASHU_BASELINE_BASE_URL is not set: the LLM baselines need a real model "
            "endpoint, and will not fall back to the stub"
        )
    api = Path(__file__).resolve().parents[2] / "services" / "api"
    if str(api) not in sys.path:
        sys.path.insert(0, str(api))
    from app.engines.providers.openaicompat import OpenAICompatProvider

    provider = OpenAICompatProvider(
        model=model,
        base_url=base_url,
        api_key_env="PASHU_BASELINE_API_KEY",
        requires_key=bool(os.environ.get("PASHU_BASELINE_API_KEY")),
        timeout=180.0,
        temperature=float(os.environ.get("PASHU_BASELINE_TEMPERATURE", "0.2")),
    )
    return Gateway(provider=provider, breaker=CircuitBreaker())
