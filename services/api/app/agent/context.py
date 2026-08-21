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

from pashupatastra.gateway import Evidence
from pashupatastra.incidents import Incident

MAX_EVENTS = 12
MAX_AUDIT = 8


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

    for hypothesis in incident.hypotheses:
        blocks.append(
            Evidence(
                ref=f"{incident.id}#hypothesis",
                source="hypothesis",
                trusted=True,
                content=(
                    f"statement: {hypothesis.statement}\n"
                    f"confidence: {hypothesis.confidence}"
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


def audit_evidence(records, limit: int = MAX_AUDIT) -> list[Evidence]:
    """Recent audit entries — what the platform itself did, and when.

    Trusted, because the platform wrote them. This is the only category here
    that is, and it earns it by never containing text from outside.
    """
    blocks: list[Evidence] = []
    for record in records[:limit]:
        blocks.append(
            Evidence(
                # Keyed by *when*, not by position. `audit#2` was positional,
                # and the trail moves: answering a question appends an audit
                # record of its own, so by the time the page rendered, index 0
                # was the chat turn that produced the citation. A ref that
                # silently points at a different record than the one it was
                # taken from is worse than no ref at all.
                ref=f"audit:{record.at.isoformat()}",
                source="audit",
                trusted=True,
                content=(
                    f"{record.at.isoformat()} {record.kind} by {record.actor}: "
                    f"{record.summary}"
                ),
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


def build(incident: Incident, store, audit) -> list[Evidence]:
    """Everything known about one incident, ready to be fenced."""
    return [
        *incident_evidence(incident),
        *event_evidence(store, cited_event_ids(incident)),
        *audit_evidence(audit.records(incident_ref=incident.id, limit=MAX_AUDIT)),
    ]
