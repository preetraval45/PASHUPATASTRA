"""Who Sati is when it is answering a stranger.

One role, declared once, so that "what may this agent do" has a single answer
that a reader can check — rather than being distributed across a tool list here,
a risk comparison there, and a sentence in a prompt.

`AgentSpec` already carries both halves and `may_use` already states the rule
this depends on: *a tool absent from the declaration is unreachable, not
discouraged.* Using it means the chat route inherits the same bounding that
every other agent gets, instead of a second mechanism that has to be kept in
step with the first.
"""

from __future__ import annotations

from pashupatastra import Environment
from pashupatastra.agents import AgentSpec

ANALYST = AgentSpec(
    name="sati.analyst",
    role="analyst",
    environments=[Environment.DEV, Environment.STAGING, Environment.PROD],
    tools=["get_entity", "blast_radius", "read_logs", "lookup_advisory"],
    # Zero, and not as a placeholder. `agent_risk_limit` caps what may be
    # authorised without a human, so zero sends every action carrying any risk
    # at all back for approval — the correct setting for an agent whose input
    # arrives from an unauthenticated text box on the public internet.
    #
    # Deliberately stricter than a human operator's path, which is allowed: the
    # rule is that AI-initiated actions get no *weaker* path than human ones,
    # not that the two are identical.
    risk_limit=0,
    goals=[
        "Explain an incident from stored evidence",
        "Name the action a request would require, and route it to a human",
    ],
)
