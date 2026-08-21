"""One chat turn, end to end.

The shape is: retrieve deterministically, ask, then **check the citations**.

That last step is the one doing real work. A model asked to cite its sources
will cite something whether or not it read anything, and a citation nobody
verifies is decoration. Every ref an answer returns is matched against what was
actually retrieved this turn — the evidence blocks, plus whatever the tools
brought back. Refs that do not match are removed, and an answer left with none
is reported as ungrounded rather than quietly presented as sourced.

This is rule 1 in CLAUDE.md made operational. The model is not the source of
truth; the store is, and the refs are the join between them.
"""

from __future__ import annotations

from datetime import datetime

from pashupatastra.gateway import (
    ConversationRequest,
    ConversationResponse,
    GatewayError,
    ToolCall,
    ToolOutcome,
)
from pydantic import BaseModel, Field

from ..config import get_settings
from . import cache as answer_cache
from . import context
from .tools import ToolBox

INSTRUCTIONS = """You are Sati, the analyst assistant on a security operations console.

You answer questions about one incident, using only the evidence supplied to \
you and the tools offered. You have no memory of other conversations and no \
access to anything beyond this incident.

Rules you follow without exception:

1. Every claim comes from the evidence. If the evidence does not contain the \
answer, set answerable to false and say what is missing. A correct "I cannot \
tell from what I have" is worth more than a plausible guess, because the person \
reading you cannot check the guess.
2. Cite the refs you used, exactly as they appear in the evidence headers. Refs \
are verified against what was actually retrieved. An invented ref is removed \
and marks the whole answer ungrounded, so guessing one makes your answer weaker.
3. You cannot act. You cannot isolate a host, block an address, disable an \
account or page anyone. If asked to, explain that the action has to go through \
policy evaluation and human approval, and say which action it would be.
4. Be brief and concrete. An analyst is reading you mid-incident.
"""

PURPOSE = "chat"


class ChatAnswer(BaseModel):
    """What one turn produced, including how much of it can be trusted."""

    answer: str
    evidence_refs: list[str] = Field(default_factory=list)
    answerable: bool = True
    grounded: bool = True
    """False when nothing the answer cited could be resolved. A reader should
    weigh the two differently, so they are two fields rather than one."""

    dropped_refs: list[str] = Field(default_factory=list)
    """Refs the model returned that matched nothing retrieved. Surfaced rather
    than swallowed: a model citing sources it did not read is worth seeing."""

    trace: list[dict] = Field(default_factory=list)
    tokens: int = 0
    model: str = ""
    provider: str = ""
    truncated: bool = False
    cached: bool = False
    """True when this turn cost nothing. Shown rather than hidden — a reader
    deciding how current an answer is should know it was computed earlier."""


def _verify(refs: list[str], available: set[str]) -> tuple[list[str], list[str]]:
    """Split what the model cited into resolvable and not.

    Matching is exact. A prefix or fuzzy match would let `INC-2026-0901#chain-9`
    resolve against `INC-2026-0901`, which is precisely the kind of near-miss
    citation that reads as specific and is not.
    """
    kept, dropped = [], []
    for ref in refs:
        (kept if ref in available else dropped).append(ref)
    return kept, dropped


def answer(
    incident,
    message: str,
    store,
    graph,
    audit,
    gateway,
    now: datetime | None = None,
) -> ChatAnswer:
    """Answer one question about one incident."""
    settings = get_settings()
    evidence = context.build(incident, graph, audit)
    box = ToolBox(incident, store, graph, domain=settings.action_domain)

    # Grows as tools return. A ref only becomes citable once something has
    # actually fetched it in this conversation.
    available = {item.ref for item in evidence}

    def dispatch(call: ToolCall) -> ToolOutcome:
        outcome = box.dispatch(call)
        available.update(outcome.refs)
        return outcome

    request = ConversationRequest(
        purpose=PURPOSE,
        instructions=INSTRUCTIONS,
        visitor_message=message,
        schema_name="chat_answer_v1",
        evidence=evidence,
        tools=box.specs(),
        incident_id=incident.id,
        agent="sati.analyst",
        max_tokens=settings.chat_answer_tokens,
        token_ceiling=settings.chat_token_ceiling,
        max_hops=settings.chat_max_tool_hops,
    )

    digest = answer_cache.key(
        incident_id=incident.id,
        question=message,
        model=getattr(gateway.provider, "model", ""),
        instructions=INSTRUCTIONS,
        evidence_refs=sorted(available),
    )
    cache = answer_cache.shared(getattr(store, "_durable", lambda: None)())
    hit = cache.get(digest)
    if hit is not None:
        # Costs nothing and hits no rate limit. On a public console most
        # questions are the same question, so this is the difference between a
        # demo that survives a burst of visitors and one that starts refusing.
        return ChatAnswer(**{**hit, "cached": True})

    response: ConversationResponse = gateway.converse(request, dispatch)

    output = response.output
    kept, dropped = _verify(list(output.get("evidence_refs") or []), available)
    answerable = bool(output.get("answerable", True))

    result = ChatAnswer(
        answer=str(output.get("answer") or "").strip(),
        evidence_refs=kept,
        answerable=answerable,
        # An answer that claims to be unanswerable is not ungrounded for having
        # cited nothing — there was nothing to cite, which is the honest case.
        grounded=bool(kept) or not answerable,
        dropped_refs=dropped,
        trace=[entry.model_dump(mode="json", exclude_none=True) for entry in response.trace],
        tokens=response.usage.total_tokens,
        model=response.model,
        provider=response.provider,
        truncated=response.truncated,
    )

    # Only answers worth repeating. A truncated or ungrounded turn is a bad
    # answer, and caching it would serve that bad answer to everyone who asks
    # the same thing rather than giving the next visitor a fresh attempt.
    if result.grounded and not result.truncated:
        cache.put(digest, result.model_dump(mode="json"))
    return result


__all__ = ["ChatAnswer", "GatewayError", "answer"]
