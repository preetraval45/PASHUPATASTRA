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
account or page anyone. If the question asks for something to be DONE, set \
proposed_action_id to the registered action it would require and explain that \
it has been queued for a human to approve. Naming an action is not performing \
it — the id is checked against the registry, scored by the policy engine, and \
put in an approval queue. Never claim to have done anything.
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

    proposed_action_id: str | None = None
    """The action the question would require, if it asked for one. Validated
    against the registry — a name the model invented is discarded the same way
    an invented citation is, because a proposal nobody can look up is not a
    proposal."""

    verdict: dict | None = None
    """Dharma's scoring of that proposal, filled in by the route. The chat
    engine deliberately does not evaluate it: policy is Dharma's to decide, and
    an engine that scored its own proposals would be marking its own work."""

    approval_id: str | None = None
    """Set when the proposal was queued for a human."""

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


def _known_action(action_id) -> str | None:
    """Keep a proposed action id only if the registry has it.

    The same discipline as citations, for the same reason. A model naming
    `quarantine_host` — plausible, and not an action here — would otherwise
    produce an approval request for something that cannot be executed, reviewed
    or rolled back.
    """
    if not action_id or not isinstance(action_id, str):
        return None
    from pashupatastra.registry import get as get_action

    try:
        get_action(action_id)
    except KeyError:
        return None
    return action_id


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
    # A turn that proposed an action is never served from cache: the proposal
    # has to reach the approval queue every time somebody asks for it, and a
    # cached copy would answer "queued for approval" without queueing anything.
    if hit is not None and not hit.get("proposed_action_id"):
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
        proposed_action_id=_known_action(output.get("proposed_action_id")),
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
    if result.grounded and not result.truncated and result.proposed_action_id is None:
        cache.put(digest, result.model_dump(mode="json"))
    return result


__all__ = ["ChatAnswer", "GatewayError", "answer"]
