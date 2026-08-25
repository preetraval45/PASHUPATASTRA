"""Blue team mode: the incident, played forwards.

The console shows a finished investigation — chain, diagnosis, plan, verdict. It
is a good way to read what happened and a poor way to learn how anyone got
there, because every hard choice has already been made and is presented as
obvious. This inverts it: one alert, and the rest is the player's.

**The answer stays on the server.** A briefing carries the opening alert, the
entities that can be looked at, the candidate explanations and the actions
available — and nothing that says which explanation is right. That is not
anti-cheat theatre; it is that a page which ships the answer in its own payload
teaches the player to open dev tools, and the thing being taught here is how to
reason from evidence.

Scoring has three parts because getting an incident right has three parts, and
they fail independently. A player can name the right cause and reach for a
sledgehammer. A player can pick the proportionate action for the wrong reason.
And a player can be right by luck, having never looked at the evidence that
rules the plausible alternative out — which is the one this is really teaching,
because in a real incident the plausible alternative is what a tired analyst
takes.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pashupatastra.incidents import Incident
from pashupatastra.registry import all_actions, get as get_action

DIAGNOSIS_POINTS = 50
RESPONSE_POINTS = 30
INVESTIGATION_POINTS = 20

MAX_ACTIONS_OFFERED = 8


def _stable_order(values: list[str]) -> list[str]:
    """A shuffle that is the same on every load and uncorrelated with truth.

    Randomising per request would move the options under a player who reloads.
    Leaving them in source order puts the correct explanation first every time,
    which is not a difficulty setting, it is the answer. Hashing the statement
    gives an order that is arbitrary, stable, and independent of which one is
    right.
    """
    return sorted(values, key=lambda text: hashlib.sha256(text.encode()).hexdigest())


def opening_alert(incident: Incident, graph) -> dict[str, Any] | None:
    """The earliest signal, and only that one.

    Chronological rather than "the first in the chain": the chain is the
    conclusion, written after the fact. An analyst gets whichever alert fired
    first, which is often the least informative one in the incident.
    """
    refs = [ref for link in incident.causal_chain for ref in link.evidence]
    rows = [row for ref in refs if (row := graph.event(ref)) is not None]
    if not rows:
        return None
    first = min(rows, key=lambda row: str(row.get("occurred_at", "")))
    payload = first.get("payload") or {}
    return {
        "id": first["id"],
        "at": first.get("occurred_at"),
        "entity_key": first.get("entity_key"),
        "severity": first.get("severity"),
        "detection": payload.get("detection_type") or first.get("event_class"),
        "summary": (first.get("labels") or {}).get("summary")
        or payload.get("message")
        or payload.get("summary")
        or "",
    }


def investigable(incident: Incident) -> list[str]:
    """What the player may look at, in an order that gives nothing away.

    Sorted, not chain order. The sequence of the causal chain *is* the answer to
    "how did this unfold", and listing the options in it would hand that over on
    the briefing screen.
    """
    keys = {entity.key() for entity in incident.affected_entities}
    keys |= {link.entity.key() for link in incident.causal_chain}
    return sorted(keys)


def candidates(incident: Incident) -> list[dict[str, str]]:
    """The explanations on offer, stripped of every tell.

    No confidence, no contradictions, no ordering by likelihood. Those three
    fields are how the console shows a finished diagnosis, and any one of them
    left in turns this into a reading comprehension exercise.
    """
    statements = _stable_order([h.statement for h in incident.hypotheses])
    return [{"id": _choice_id(text), "statement": text} for text in statements]


def _choice_id(statement: str) -> str:
    return hashlib.sha256(statement.encode()).hexdigest()[:12]


def _inverses_of_plan(incident: Incident, catalogue: dict[str, Any]) -> set[str]:
    """The undo of each planned action.

    There is no way to ask the registry which half of a pair is the *undo*,
    because the relationship is mutual: `isolate_host` names `rejoin_network` as
    its rollback and `rejoin_network` names `isolate_host` as its. An earlier
    version excluded anything that appeared as some action's
    `rollback_action_id`, which is every action in every reversible pair — and
    so removed `isolate_host`, `block_ip`, `revoke_session` and
    `quarantine_email` from the menu. The correct answers. The exercise could
    not be won, and nothing said so.

    What can be identified precisely is narrower and is the only exclusion worth
    making: the inverse of what the plan calls for. Offering *rejoin the
    network* as a response to a live intrusion is not a distractor, it is
    nonsense, and a menu of nonsense teaches a player to pattern-match rather
    than to weigh.
    """
    inverses = set()
    for step in incident.plan:
        action = catalogue.get(step.action_id)
        if action is not None and action.rollback_action_id:
            inverses.add(action.rollback_action_id)
    return inverses


def offered_actions(incident: Incident, domain=None) -> list[dict[str, Any]]:
    """The menu, built so that every score is reachable.

    Composed, not sliced. The first version sorted the registry by risk and took
    the cheapest eight, which produced a list of read-only actions and rate
    limits and left `isolate_host` off the menu for a beaconing workstation:
    the response dimension could not be scored above a third because the
    proportionate answer was not on offer. **A menu has to contain the right
    answer to be a test of anything.**

    So: what the plan called for, something that does too little, something that
    does far too much, and enough plausible middle ground that the right one is
    not identifiable as the only serious option present.
    """
    catalogue = {action.id: action for action in all_actions(domain=domain)}
    excluded = _inverses_of_plan(incident, catalogue)

    chosen: dict[str, Any] = {}

    def offer(action_id: str) -> None:
        action = catalogue.get(action_id)
        if action is not None and action.id not in excluded:
            chosen[action.id] = action

    # The proportionate answer. Without these the exercise is unwinnable.
    for step in incident.plan:
        offer(step.action_id)

    # Doing too little, and doing far too much. Both are answers a real analyst
    # gives under pressure, and neither can be marked if neither is offered.
    offer("read_logs")
    offer("wipe_host")

    # Plausible middle ground, cheapest first.
    for action in sorted(catalogue.values(), key=lambda a: a.base_risk):
        if len(chosen) >= MAX_ACTIONS_OFFERED:
            break
        if action.id in excluded or action.read_only:
            continue
        chosen.setdefault(action.id, action)

    return [
        {
            "id": action.id,
            "description": action.description,
            "base_risk": action.base_risk,
            "read_only": action.read_only,
        }
        for action in sorted(chosen.values(), key=lambda a: a.base_risk)
    ]


def briefing(incident: Incident, graph, domain=None) -> dict[str, Any]:
    alert = opening_alert(incident, graph)
    return {
        "incident_id": incident.id,
        "opened_at": incident.opened_at.isoformat(),
        "alert": alert,
        "entities": investigable(incident),
        "candidates": candidates(incident),
        "actions": offered_actions(incident, domain),
        "scoring": {
            "diagnosis": DIAGNOSIS_POINTS,
            "response": RESPONSE_POINTS,
            "investigation": INVESTIGATION_POINTS,
        },
    }


def investigate(incident: Incident, graph, entity_key: str, limit: int = 8) -> dict[str, Any]:
    """What is known about one entity — the evidence, not the conclusion.

    Restricted to entities in this incident. An open-ended entity lookup on a
    public console is an interface for asking which of our hosts and accounts
    exist, and a game is not a reason to open one.
    """
    if entity_key not in investigable(incident):
        return {"ok": False, "reason": "not part of this incident", "events": []}

    rows = graph.entity_events(entity_key, limit=limit)
    node = graph.entity(entity_key) if hasattr(graph, "entity") else None
    return {
        "ok": True,
        "entity": node,
        "events": [
            {
                "id": row["id"],
                "at": row.get("occurred_at"),
                "severity": row.get("severity"),
                "detection": (row.get("payload") or {}).get("detection_type"),
                "summary": (row.get("labels") or {}).get("summary")
                or (row.get("payload") or {}).get("message")
                or "",
            }
            for row in rows
        ],
    }


# --- scoring ------------------------------------------------------------------


def _correct(incident: Incident):
    """The intended explanation: highest confidence, nothing contradicting it."""
    return max(incident.hypotheses, key=lambda h: h.confidence, default=None)


def _decoy(incident: Incident):
    """The plausible wrong one — the alternative something rules out.

    Identified by *having* contradicting evidence rather than by position. A
    scenario written later with three alternatives still works, and a scenario
    that forgets to contradict its decoy scores no investigation points rather
    than silently marking the wrong hypothesis as the trap.
    """
    others = [h for h in incident.hypotheses if h.contradicted_by]
    return max(others, key=lambda h: h.confidence, default=None)


def _response_score(incident: Incident, action_id: str) -> tuple[int, str]:
    """How well the chosen action fits what is happening.

    Judged against the incident's own plan rather than a table of good actions,
    because proportionality is a property of the pair. Isolating a host is
    correct for a beaconing workstation and an overreaction to one failed login.
    """
    planned = {step.action_id for step in incident.plan}
    try:
        action = get_action(action_id)
    except KeyError:
        return 0, "That is not a registered action."

    if action_id in planned:
        return RESPONSE_POINTS, (
            "Proportionate: this is what the plan called for."
        )

    plan_risk = max(
        (get_action(step.action_id).base_risk for step in incident.plan), default=0
    )
    if action.read_only:
        return RESPONSE_POINTS // 3, (
            "Too little. Reading is how you find out, not how you stop it — "
            "the intrusion continues while you look."
        )
    if action.irreversible or action.base_risk > plan_risk + 20:
        return 0, (
            f"Disproportionate. {action.id} scores {action.base_risk} against a "
            f"plan whose riskiest step is {plan_risk}; the damage of the response "
            "would exceed the damage of the incident."
        )
    return RESPONSE_POINTS // 2, (
        "Defensible, but not what the plan called for — it addresses part of "
        "this and leaves the rest running."
    )



def _debrief(incident: Incident, graph, looked_at: set[str], decisive: set[str]) -> dict:
    """What the player opened, what they did not, and what was in each.

    R64's point, and the reason a total is not a debrief: *"you scored 60"*
    teaches nothing, and *"you never opened `host:app-07`, which is where the
    scheduled task was recorded"* teaches the whole lesson. The training value
    is entirely in naming the thing that was missed.

    Every entity in the exercise appears in exactly one of the two lists, so the
    lists together are the full board rather than a highlight reel — a debrief
    that showed only the decisive miss would let a player conclude they had
    covered everything else.
    """
    opened: list[dict] = []
    missed: list[dict] = []

    for key in investigable(incident):
        rows = graph.entity_events(key, limit=8) or []
        refs = [row["id"] for row in rows if row.get("id")]
        held = sorted(set(refs) & decisive)
        entry = {
            "entity_key": key,
            "evidence": refs,
            # Decisive means: this entity held one of the observations that rule
            # out the plausible-but-wrong explanation. It is the difference
            # between being right and being right by luck.
            "decisive": bool(held),
            "decisive_evidence": held,
        }
        (opened if key in looked_at else missed).append(entry)

    return {
        "opened": opened,
        "missed": missed,
        # Named separately because it is the one list a player should re-read.
        "decisive_evidence": sorted(decisive),
    }


def score(
    incident: Incident,
    graph,
    diagnosis_id: str,
    action_id: str,
    investigated: list[str],
) -> dict[str, Any]:
    """Mark one attempt and reveal the answer.

    `investigated` is taken from the client on trust. There is nothing to
    protect: a player who claims to have looked at evidence they skipped has
    only awarded themselves points in a training exercise, and the alternative
    is server-side session state for a game with no stakes.
    """
    correct = _correct(incident)
    decoy = _decoy(incident)
    chosen = next(
        (h for h in incident.hypotheses if _choice_id(h.statement) == diagnosis_id),
        None,
    )

    right = chosen is not None and correct is not None and chosen.statement == correct.statement
    diagnosis_points = DIAGNOSIS_POINTS if right else 0

    response_points, response_note = _response_score(incident, action_id)

    # Did they look at what rules the decoy out?
    #
    # This is the part the exercise is actually for. The decoy is plausible;
    # what makes it wrong is a specific piece of evidence, and an analyst who
    # never opened it was right by luck.
    contradicting = set(decoy.contradicted_by) if decoy else set()
    looked_at = set(investigated or [])
    entities_with_proof = {
        row_entity
        for ref in contradicting
        if (row := graph.event(ref)) is not None
        and (row_entity := row.get("entity_key")) is not None
    }
    found_proof = bool(entities_with_proof & looked_at)
    investigation_points = INVESTIGATION_POINTS if found_proof else 0

    total = diagnosis_points + response_points + investigation_points

    # Every line of the breakdown carries what it was judged against: refs for
    # the two that rest on evidence, action ids for the one that rests on a
    # decision. R64's rule is that a point gained or lost has to trace to a
    # named thing — a number with a sentence beside it is still a number.
    supporting = sorted(set(correct.evidence)) if correct else []
    against_choice = (
        sorted(set(chosen.contradicted_by)) if chosen is not None and not right else []
    )
    debrief = _debrief(incident, graph, looked_at, contradicting)

    return {
        "total": total,
        "grade": _grade(total),
        "debrief": debrief,
        "breakdown": [
            {
                "name": "Diagnosis",
                "points": diagnosis_points,
                "of": DIAGNOSIS_POINTS,
                "note": (
                    "You identified what actually happened."
                    if right
                    else "That is not what the evidence supports."
                ),
                # What the correct diagnosis rests on, and — when the player
                # chose otherwise — what rules their choice out. Named, so the
                # sentence above can be checked rather than believed.
                "evidence": supporting,
                "contradicted_by": against_choice,
            },
            {
                "name": "Response",
                "points": response_points,
                "of": RESPONSE_POINTS,
                "note": response_note,
                # A decision, not a citation: what they chose, against what the
                # plan called for.
                "chose_action": action_id,
                "plan_actions": [step.action_id for step in incident.plan],
            },
            {
                "name": "Investigation",
                "points": investigation_points,
                "of": INVESTIGATION_POINTS,
                "note": (
                    "You opened the evidence that rules out the plausible "
                    "alternative."
                    if found_proof
                    else "You never looked at what rules out the alternative "
                    "explanation. On this scenario that evidence is on "
                    + (", ".join(sorted(entities_with_proof)) or "another entity")
                    + "."
                ),
                "evidence": sorted(contradicting),
                "on_entities": sorted(entities_with_proof),
                "opened": sorted(looked_at),
            },
        ],
        "chose": chosen.statement if chosen else None,
        "answer": reveal(incident, decoy, graph),
    }


def _grade(total: int) -> str:
    if total >= 90:
        return "clean"
    if total >= 70:
        return "sound"
    if total >= 40:
        return "shaky"
    return "missed"


def reveal(incident: Incident, decoy, graph) -> dict[str, Any]:
    """The chain, the technique mapping, and why the decoy was wrong.

    The last part is the one worth having. Being told the right answer teaches
    less than being shown the specific observation that killed the answer you
    were drawn to.
    """
    correct = _correct(incident)
    return {
        "diagnosis": correct.statement if correct else None,
        "confidence": correct.confidence if correct else None,
        "chain": [
            {
                "entity_key": link.entity.key(),
                "transition": link.transition,
                "technique": (
                    {
                        "id": link.attack_technique.id,
                        "name": link.attack_technique.name,
                        "tactic": link.attack_technique.tactic,
                        "url": link.attack_technique.url,
                    }
                    if link.attack_technique
                    else None
                ),
                "evidence": list(link.evidence),
            }
            for link in incident.causal_chain
        ],
        "plan": [
            {"order": step.order, "action_id": step.action_id} for step in incident.plan
        ],
        "decoy": (
            {
                "statement": decoy.statement,
                "ruled_out_by": [
                    {
                        "id": ref,
                        "summary": (row.get("labels") or {}).get("summary")
                        or (row.get("payload") or {}).get("message")
                        or "",
                        "entity_key": row.get("entity_key"),
                    }
                    for ref in decoy.contradicted_by
                    if (row := graph.event(ref)) is not None
                ],
            }
            if decoy
            else None
        ),
    }
