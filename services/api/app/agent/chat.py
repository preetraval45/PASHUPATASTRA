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

import hashlib
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
you and the tools offered. You have no memory of other conversations. The one \
thing you can see beyond this incident is whether another one touched the same \
hosts, accounts or addresses, and only through the tool that compares them.

Rules you follow without exception:

1. **Look before you decline.** Before saying you cannot answer, name the one \
fact that would settle the question and check whether a tool returns it. If a \
tool takes an entity key and the question is about an entity, call it. Where \
the evidence mentions something without detailing it — "two previously-unseen \
hosts", "a new scheduled task" — that is a reason to look it up, not a reason \
to stop. You have several lookups per question and spending them is what they \
are for.
2. Every claim comes from the evidence, or from what a tool returned this turn. \
If neither holds the answer *after you have looked*, set answerable to false \
and say what is missing. A correct "I cannot tell from what I have" is worth \
more than a plausible guess, because the person reading you cannot check the \
guess — but declining a question your own tools cover is not caution, it is a \
search box that apologises.
3. Cite the refs you used, exactly as they appear in the evidence headers. Refs \
are verified against what was actually retrieved. An invented ref is removed \
and marks the whole answer ungrounded, so guessing one makes your answer weaker.
4. You cannot act. You cannot isolate a host, block an address, disable an \
account or page anyone. If the question asks for something to be DONE, set \
proposed_action_id to the registered action it would require and explain that \
it has been queued for a human to approve. Naming an action is not performing \
it — the id is checked against the registry, scored by the policy engine, and \
put in an approval queue. Never claim to have done anything.
5. **On vulnerabilities and indicators, what you remember does not count.** \
You have read about CVEs during training. Those recollections are stale, \
unversioned, and impossible for the reader to check, and this console exists to \
be checkable. If an advisory for the identifier is in the evidence, answer from \
it and cite it. If it is not, say plainly that there is no stored advisory for \
that identifier and that you will not answer from memory — then stop. Do not \
describe the vulnerability, guess its severity, or say what it affects. \
"We have nothing on file for that" is a complete and correct answer.
6. **Say what else the evidence could have meant.** An evidence block headed \
`alternative reading` is an explanation this incident considered and dropped, \
and it carries a `contradicted by:` line naming the refs that dropped it. For \
every such block you are given, put it in `considered` with exactly those refs. \
This is reading the record, not forming a view — the incident already weighed \
it. Those refs are verified like any other, so one that does not resolve is \
discarded. Return an empty list only when no alternative reading was supplied, \
and never invent a rival explanation in order to knock it down.
7. **Whether two incidents are related is not yours to judge.** If you are \
asked about another incident, call `related_incidents` with its id and report \
what comes back. It compares what the two actually touched. *No relation found* \
is a complete answer and you should give it plainly — two incidents happening \
close together, or looking alike, is not a relation, and calling them linked \
because both involve a sign-in is a claim nobody can check. Never answer a \
relation question without calling the tool.
8. Be brief and concrete. An analyst is reading you mid-incident.
"""

PURPOSE = "chat"

PROMPT_VERSION = "6"
"""Bumped whenever `INSTRUCTIONS` changes in a way that changes answers.

Version 2 added the action-proposal rule (R20); version 3 added the rule that a
remembered CVE does not count as evidence (R26); version 4 made looking a step
before declining (R94). An answer is only comparable to another answer produced
under the same instructions, so this is what makes "why did it say that"
answerable a month later, when the prompt has moved on.

Version 4 exists because of a measurement rather than a hunch. Asked which
hosts `ws-0148` opened SMB to, the deployed agent answered at hop 0 with no
tool call at all — while holding `get_entity` and `blast_radius`, either of
which would have answered. The loop, the budget and the tools were all present
and all unused.

The cause was in this text. The old rule 1 said "if the evidence does not
contain the answer, set answerable to false" and never mentioned looking.
`lookup_advisory` is the control that proves it: the one tool with a rule
pointing at it is the one that got called.

Version 5 added rule 6 (R68): name the readings that were open and what closed
them. An answer that only states its conclusion is asking to be believed; the
console's argument is that it can be checked instead.

Rule 6 points at the *shape of an evidence block* rather than at the idea, for
the reason recorded under version 4: `lookup_advisory` was the one tool with a
rule pointing directly at it and the one tool that got called. Two drafts were
measured against the live model before this one. The first described the
principle; the second added the block shape but left the instruction
conditional — *when your answer depends on one of those being wrong* — and both
returned an empty list on the question this incident exists to pose: "could the
user just be travelling?", with the contradicted alternative sitting in the
evidence under its own ref. The same model filled the field first time when
told plainly to. A conditional rule is one the model gets to decide it has
already satisfied.

Version 6 added rule 7 (R69) and narrowed the opening claim, which had said the
agent has "no access to anything beyond this incident" — untrue the moment a
tool can compare it with another one, and a prompt that misdescribes its own
tools is a prompt arguing against using them.
"""


def prompt_digest() -> str:
    """A fingerprint of the instructions actually in force.

    The version above is written by hand, so it is wrong exactly when someone
    edits the prompt and forgets to bump it — which is the case where a reader
    most needs to know. The digest cannot be forgotten: two turns claiming
    version 2 with different digests are visibly not the same prompt.
    """
    return hashlib.sha256(INSTRUCTIONS.encode("utf-8")).hexdigest()[:12]


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

    considered: list[dict] = Field(default_factory=list)
    """Other readings of the evidence, each with the refs that closed it.

    Held to the same standard as a citation and for the same reason: an
    alternative "ruled out" by a ref nobody can resolve is the appearance of
    rigour rather than rigour. What survives verification is a rejection a
    reader can check; what does not is in `dropped_considered`."""

    dropped_considered: list[dict] = Field(default_factory=list)
    """Alternatives that named nothing resolvable as their reason. Kept for the
    same reason `dropped_refs` is: a model dismissing readings on evidence it
    did not read is worth seeing, and deleting it would make the answer look
    tidier than it was."""

    trace: list[dict] = Field(default_factory=list)
    tokens: int = 0
    model: str = ""
    provider: str = ""
    truncated: bool = False
    prompt_version: str = PROMPT_VERSION
    prompt_digest: str = ""
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


def _considered(raw, available: set[str]) -> tuple[list[dict], list[dict]]:
    """Split the weighed alternatives into checkable rejections and the rest.

    An alternative survives only if at least one ref it names as the reason
    resolves against what was actually retrieved. Two failures are collapsed
    here deliberately, because they are the same failure: naming no reason at
    all, and naming a reason that does not exist. Both leave a reader with a
    rejection they cannot check, which on this console is worth less than no
    rejection at all — it spends the reader's trust without earning it.

    The refs that did not resolve are kept on the dropped entry rather than
    discarded, so the record shows what was claimed as well as that it failed.
    """
    kept: list[dict] = []
    dropped: list[dict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        reading = str(item.get("reading") or "").strip()
        if not reading:
            continue
        refs = [str(ref) for ref in (item.get("ruled_out_by") or []) if isinstance(ref, str)]
        resolved = [ref for ref in refs if ref in available]
        unresolved = [ref for ref in refs if ref not in available]
        if resolved:
            entry = {"reading": reading, "ruled_out_by": resolved}
            if unresolved:
                entry["dropped_refs"] = unresolved
            kept.append(entry)
        else:
            dropped.append({"reading": reading, "claimed_refs": refs})
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
    evidence = context.build(incident, graph, audit, message=message)
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

    # Every ref here is stable — chain steps, plan steps, event ids. That was
    # not true while the audit trail was evidence: its refs are timestamps and
    # answering appends a record, so the key changed on every request and the
    # cache never hit once. See `context.build` for why the trail left.
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
    considered, dropped_considered = _considered(output.get("considered"), available)
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
        considered=considered,
        dropped_considered=dropped_considered,
        trace=[entry.model_dump(mode="json", exclude_none=True) for entry in response.trace],
        tokens=response.usage.total_tokens,
        model=response.model,
        provider=response.provider,
        truncated=response.truncated,
        prompt_version=PROMPT_VERSION,
        prompt_digest=prompt_digest(),
    )

    # Only answers worth repeating. A truncated or ungrounded turn is a bad
    # answer, and caching it would serve that bad answer to everyone who asks
    # the same thing rather than giving the next visitor a fresh attempt.
    if result.grounded and not result.truncated and result.proposed_action_id is None:
        cache.put(digest, result.model_dump(mode="json"))
    return result


__all__ = ["ChatAnswer", "GatewayError", "answer"]
