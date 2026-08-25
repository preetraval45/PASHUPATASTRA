"""What the agent is told before it is asked anything.

Retrieval is deterministic and happens up front, every turn. The model does not
have to decide to look something up in order to be grounded — tools exist to
fetch *more*, never to fetch the basics. Two reasons, and the second is the one
that matters:

- A provider with no tool support still answers from real data.
- Rule 1 in CLAUDE.md. If grounding depended on the model choosing to retrieve,
  then the model choosing not to would produce an ungrounded answer that looks
  exactly like a grounded one.

Everything returned here is `Evidence` with a `ref` that resolves through the
same routes the dashboard links to, so any claim built on it can be checked by a
human clicking through. Refs that cannot be resolved are not emitted: evidence
nobody can retrieve is indistinguishable from evidence nobody has.
"""

from __future__ import annotations

import re

from pashupatastra.gateway import Evidence
from pashupatastra.incidents import Incident

MAX_EVENTS = 12
MAX_INTEL = 4

CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
"""The one identifier worth extracting from a question.

Deliberately narrow. A looser pattern — hostnames, addresses — would turn every
question into a lookup of whatever string it happened to contain, and on a
public console that is an interface for asking which of *our* entities exist.
A CVE id is a public identifier for a public document, so resolving one gives
away nothing.
"""


def incident_evidence(incident: Incident) -> list[Evidence]:
    """The incident itself, one block per fact worth citing separately.

    Split rather than dumped as a single JSON blob so that citations land on
    something specific. `INC-2026-0901` as a ref tells a reader which incident;
    `INC-2026-0901#chain-2` tells them which step of the reasoning.
    """
    blocks: list[Evidence] = [
        Evidence(
            ref=incident.id,
            source="incident",
            trusted=True,
            content=(
                f"id={incident.id} state={incident.state} "
                f"severity={incident.severity} opened_at={incident.opened_at.isoformat()}\n"
                f"affected entities: "
                f"{', '.join(e.key() for e in incident.affected_entities) or 'none recorded'}\n"
                f"estimated users affected: {incident.impact.estimated_users_affected}\n"
                f"blast radius entities: {incident.impact.blast_radius_entities}"
            ),
        )
    ]

    for index, link in enumerate(incident.causal_chain):
        technique = (
            f" technique={link.attack_technique.id} ({link.attack_technique.name}, "
            f"{link.attack_technique.tactic})"
            if link.attack_technique
            else ""
        )
        blocks.append(
            Evidence(
                ref=f"{incident.id}#chain-{index}",
                source="causal_chain",
                trusted=True,
                content=(
                    f"step {index + 1} of {len(incident.causal_chain)}: "
                    f"{link.entity.key()} — {link.transition}{technique}\n"
                    f"supported by: {', '.join(link.evidence)}"
                ),
            )
        )

    # Ranked, so "the leading reading" and "the one that was considered and
    # dropped" are distinguishable. They were not: every hypothesis went over
    # under the same ref, `#hypothesis`, which gave two opposite claims one
    # identifier — a citation that cannot say which of them it means.
    ranked = sorted(incident.hypotheses, key=lambda h: h.confidence, reverse=True)
    for index, hypothesis in enumerate(ranked):
        # `contradicted_by` is the field this console's argument rests on — the
        # system showing its own doubt — and it was stripped before the agent
        # saw it. Sati was reasoning from a diagnosis with the doubt removed,
        # and could not have named what ruled an alternative out because it was
        # never told there was an alternative.
        against = (
            f"\ncontradicted by: {', '.join(hypothesis.contradicted_by)}"
            if hypothesis.contradicted_by
            else ""
        )
        blocks.append(
            Evidence(
                ref=f"{incident.id}#hypothesis-{index}",
                source="hypothesis",
                trusted=True,
                content=(
                    f"{'leading reading' if index == 0 else 'alternative reading'}: "
                    f"{hypothesis.statement}\n"
                    f"confidence: {hypothesis.confidence}\n"
                    f"supported by: {', '.join(hypothesis.evidence)}"
                    f"{against}"
                ),
            )
        )

    for step in incident.plan:
        verdict = step.verdict
        blocks.append(
            Evidence(
                ref=f"{incident.id}#plan-{step.order}",
                source="plan",
                trusted=True,
                content=(
                    f"step {step.order}: {step.action_id}\n"
                    f"rollback: {step.rollback_action_id or 'none declared'}\n"
                    f"policy verdict: "
                    + (
                        f"{verdict.tier} at risk {verdict.effective_risk}"
                        if verdict
                        else "not evaluated"
                    )
                ),
            )
        )

    return blocks


def event_evidence(store, event_ids: list[str], limit: int = MAX_EVENTS) -> list[Evidence]:
    """The events the incident cites, as themselves.

    `trusted=False`, and that is the whole point of the flag. A log line holds
    whatever was written to it, including by whoever caused the incident, so
    this is the text most likely to be carrying an instruction aimed at the
    model reading it.
    """
    blocks: list[Evidence] = []
    for event_id in event_ids[:limit]:
        row = store.event(event_id)
        if row is None:
            # Silently skipped. A ref the evidence route cannot resolve is a
            # citation that dead-ends for whoever clicks it.
            continue
        payload = row.get("payload") or {}
        summary = payload.get("message") or payload.get("summary") or ""
        blocks.append(
            Evidence(
                ref=event_id,
                source=row.get("source") or "event",
                content=(
                    f"class={row.get('event_class')} severity={row.get('severity')} "
                    f"entity={row.get('entity_key')} at={row.get('occurred_at')}\n"
                    f"{summary}".strip()
                ),
            )
        )
    return blocks


def identifiers(message: str) -> list[str]:
    """Vulnerability ids mentioned in a question, uppercased and deduplicated."""
    seen: list[str] = []
    for match in CVE.findall(message or ""):
        upper = match.upper()
        if upper not in seen:
            seen.append(upper)
    return seen[:MAX_INTEL]


def _advisory_lines(identifier: str, row: dict) -> list[str]:
    """One advisory, as lines. Built as a list rather than a chain of
    conditional f-strings because half of these fields are absent on any given
    entry — KEV has a remediation deadline, URLhaus has none — and the version
    that concatenated optionals was unreadable before it was wrong."""
    labels = row.get("labels") or {}
    provenance = row.get("provenance") or {}

    lines = [
        f"{identifier} — {labels.get('title', '')}".strip(),
        f"verification: {labels.get('verification', 'unknown')} "
        f"(published by {provenance.get('source_system', 'unknown')})",
        f"added to the catalogue: {provenance.get('offset', 'unknown')}",
    ]
    if labels.get("summary"):
        lines.append(labels["summary"])
    if labels.get("required_action"):
        lines.append(f"required action: {labels['required_action']}")
    if labels.get("due_date"):
        lines.append(f"federal remediation due: {labels['due_date']}")
    if labels.get("ransomware") == "known":
        lines.append("known use in ransomware campaigns")
    lines.append(f"advisory: {provenance.get('url', 'none recorded')}")
    return lines


def intel_evidence(graph, message: str, limit: int = MAX_INTEL) -> list[Evidence]:
    """Stored advisories for identifiers the question mentions.

    Retrieved **before** the model is asked, not by the model deciding to look.
    That ordering is the whole of R26: a model asked about `CVE-2026-0001`
    already has an opinion from training, and an opinion is what it gives if
    nothing better is in front of it. Putting the stored entry in the prompt
    makes the grounded answer the easy one rather than the disciplined one.

    Untrusted, like all evidence. The text originates with CISA or abuse.ch —
    reputable, and still not us.

    An identifier with no stored entry produces **no block at all**. The
    temptation is to emit "nothing on file for CVE-X", and that hands the model
    a ref to cite for a claim about nothing — an answer that looks grounded
    while resting on an absence. The instructions cover the missing case in
    words instead.
    """
    blocks: list[Evidence] = []
    for identifier in identifiers(message)[:limit]:
        rows = (
            graph.entity_events(f"vulnerability:{identifier}", limit=1)
            if hasattr(graph, "entity_events")
            else []
        )
        if not rows:
            continue
        row = rows[0]
        blocks.append(
            Evidence(
                ref=row["id"],
                source=row.get("source") or "intel",
                content="\n".join(_advisory_lines(identifier, row)),
            )
        )
    return blocks


def cited_event_ids(incident: Incident) -> list[str]:
    """Every event id the incident points at, in the order it points at them.

    Reads the causal chain as well as `event_ids`, because on these incidents
    `event_ids` is empty and every reference lives on a chain step. Taking only
    the former produced a context with no telemetry in it at all — and nothing
    failed, because an incident summary reads perfectly well without the events
    it was derived from. The answers were just thinner than they looked.
    """
    seen: list[str] = []
    for ref in [*incident.event_ids, *(r for link in incident.causal_chain for r in link.evidence)]:
        if ref not in seen:
            seen.append(ref)
    return seen


def build(incident: Incident, store, audit=None, message: str = "") -> list[Evidence]:
    """Everything known about one incident, ready to be fenced.

    **The audit trail is deliberately not here.** It was, and it caused three
    separate problems that all had the same root: the trail moves while the
    page does not.

    - Its citations could never resolve. The page renders anchors for the
      records that existed when it was rendered; the agent cites the records
      that exist when it answers, which is later. A citation that 404s is worse
      than none, because it looks checkable.
    - It broke the answer cache. Refs are timestamps and answering appends a
      record, so the cache key changed on every request and never hit once —
      silently, because a cache that always misses still returns correct
      answers, at full price.
    - It fed the agent its own previous replies as observed facts.

    Nothing of substance is lost. What an analyst wants from the trail is which
    actions were proposed and how policy scored them, and the plan steps carry
    exactly that, as `#plan-N` refs that point at something stable.

    `audit` is still accepted so callers do not have to change, and ignored.
    """
    return [
        *incident_evidence(incident),
        *event_evidence(store, cited_event_ids(incident)),
        # Advisories for anything the question names. Last, because they are
        # context for the question rather than facts about the incident, and a
        # reader scanning the prompt should meet the incident first.
        *intel_evidence(store, message),
    ]
