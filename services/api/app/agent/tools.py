"""What the chat agent may reach for, and the reason the list is short.

Every tool here reads. None of them changes anything, and that is enforced by
where the list comes from rather than by asking the model nicely:

- The registry half is **derived** from `ActionSpec.read_only`. An action is
  reachable from chat only if it declared itself a read. Adding a new action
  with risk cannot accidentally widen this set, and `isolate_host` is absent
  because of what it is, not because someone remembered to exclude it.
- The retrieval half touches our own stores through read methods. There is no
  write path to reach: `Store.save` and `AuditLog.append` are not bound here.

`changes_nothing` would have been the tempting basis and is the wrong one — it
is true of `notify_analyst`, which pages a human being. See the note on
`ActionSpec.read_only`.

Everything a tool returns is fed back as untrusted data. A store read returns
log text, and log text is written by whoever was there.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from pashupatastra.dharma import ActionDomain
from pashupatastra.gateway import ToolCall, ToolOutcome, ToolSpec
from pashupatastra.registry import all_actions

MAX_ROWS = 8


def _topology(graph):
    """Whatever can walk dependencies here.

    Prefers a graph the caller supplied that can already walk — which is what
    the tests inject — and otherwise builds the `GraphStore` whose job this is.
    """
    if graph is not None and hasattr(graph, "blast_radius"):
        return graph
    from ..graph import GraphStore

    return GraphStore()


def _entity_key_schema(description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["entity_key"],
        "properties": {"entity_key": {"type": "string", "description": description}},
    }


class ToolBox:
    """The tools for one conversation, bound to one incident.

    Bound rather than global: `read_logs` on an entity unrelated to the incident
    under discussion is a different question from the one being asked, and on a
    public console it is also a way to enumerate the estate one entity at a
    time. The incident's own entities are the boundary.
    """

    def __init__(
        self,
        incident,
        store,
        graph,
        domain: ActionDomain | None = None,
        spec=None,
        topology=None,
    ) -> None:
        from .roles import ANALYST

        self.incident = incident
        self.store = store
        self.graph = graph
        self.domain = domain
        self.spec = spec or ANALYST
        # Topology comes from `GraphStore`, not from the entity store. They are
        # different stores with different jobs — one holds events, the other
        # holds edges — and only `GraphStore` answers a blast-radius walk on
        # every backend. `PostgresStore` has no `blast_radius` at all, so
        # reaching for it through `graph` works in memory and on DynamoDB and
        # raises on a Postgres deployment: a walk that is right in the two
        # places it is usually tested and absent in the third.
        self.topology = topology if topology is not None else _topology(graph)
        self._scope = {e.key() for e in incident.affected_entities}
        self._scope |= {link.entity.key() for link in incident.causal_chain}

    # --- what is offered ----------------------------------------------------

    def read_only_action_ids(self) -> list[str]:
        """The registry actions that declared themselves reads."""
        return sorted(
            action.id
            for action in all_actions(domain=self.domain)
            if action.read_only
        )

    def specs(self) -> list[ToolSpec]:
        offered = [
            ToolSpec(
                name="get_entity",
                description=(
                    "Look up one entity affected by this incident: its kind, "
                    "owner, estimated users, and when it was first and last seen."
                ),
                parameters=_entity_key_schema(
                    "Entity key such as host:ws-0148 or account:j.rivera."
                ),
            ),
            ToolSpec(
                name="blast_radius",
                description=(
                    "How far an incident at this entity could reach through "
                    "known dependencies, and how many users that touches."
                ),
                parameters=_entity_key_schema("Entity key to start the walk from."),
            ),
        ]

        offered.append(
            ToolSpec(
                name="lookup_advisory",
                description=(
                    "Look up a stored advisory for a vulnerability identifier, "
                    "such as CVE-2026-0001. Returns what was ingested from the "
                    "published catalogue, or says there is no entry. Use this "
                    "instead of recalling what you know about a CVE."
                ),
                parameters={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["identifier"],
                    "properties": {
                        "identifier": {
                            "type": "string",
                            "description": "A CVE identifier, e.g. CVE-2026-0001.",
                        }
                    },
                },
            )
        )

        offered.append(
            ToolSpec(
                name="related_incidents",
                description=(
                    "Whether another incident is related to this one. Compares "
                    "what the two touched — the same host, account or address — "
                    "and answers from stored overlap, citing the records on "
                    "both sides. Says no relation found when there is none, "
                    "which is a complete answer."
                ),
                parameters={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["incident_id"],
                    "properties": {
                        "incident_id": {
                            "type": "string",
                            "description": (
                                "The other incident, e.g. INC-2026-0902. Must be "
                                "an incident that exists."
                            ),
                        }
                    },
                },
            )
        )

        offered.append(
            ToolSpec(
                name="draft_detection_rule",
                description=(
                    "Draft a Sigma detection rule from one step of this "
                    "incident, for a MITRE technique id such as T1021.002. "
                    "Returns which telemetry field became which rule field, "
                    "which fields this telemetry could not supply, and whether "
                    "the result generalises beyond this incident. The rule "
                    "itself is rendered on the incident page — report what this "
                    "returns, do not retype the rule."
                ),
                parameters={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["technique_id"],
                    "properties": {
                        "technique_id": {
                            "type": "string",
                            "description": (
                                "A MITRE ATT&CK technique id carried by this "
                                "incident's causal chain, e.g. T1021.002."
                            ),
                        }
                    },
                },
            )
        )

        offered.append(
            ToolSpec(
                name="what_if_we_had_acted",
                description=(
                    "Estimate what acting on one of this incident's entities "
                    "earlier would have prevented, from the stored timeline and "
                    "the access graph. Defaults to the earliest moment the "
                    "records would have justified acting. Returns the steps it "
                    "would have pre-empted, the ones that would have happened "
                    "anyway, and the assumptions the estimate rests on. Refuses "
                    "a moment earlier than the first observation of that entity."
                ),
                parameters={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["entity_key"],
                    "properties": {
                        "entity_key": {
                            "type": "string",
                            "description": (
                                "An entity on this incident's causal chain, e.g. "
                                "host:ws-0148."
                            ),
                        },
                        "at": {
                            "type": "string",
                            "description": (
                                "Optional ISO timestamp to act at. Omit for the "
                                "earliest moment the records support, which is "
                                "the question worth asking."
                            ),
                        },
                    },
                },
            )
        )

        offered.append(
            ToolSpec(
                name="argue_the_other_side",
                description=(
                    "State the case for this incident's leading alternative "
                    "explanation, then report what rules it out — or that "
                    "nothing does. Takes no arguments; it reads the hypotheses "
                    "already recorded. Refuses where the incident has no rival "
                    "worth arguing rather than manufacturing one."
                ),
                parameters={
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {},
                },
            )
        )

        available = set(self.read_only_action_ids())
        if "read_logs" in available:
            offered.append(
                ToolSpec(
                    name="read_logs",
                    description=(
                        "Recent recorded events for an entity in this incident. "
                        "Returns observed telemetry, not an interpretation."
                    ),
                    parameters=_entity_key_schema("Entity key to read events for."),
                )
            )
        # The declaration is the second lock. `read_only` says an action is a
        # read; `may_use` says this agent was given it. Both have to agree, so
        # adding a read-only action to the registry does not silently widen what
        # a public text box can reach.
        return [tool for tool in offered if self.spec.may_use(tool.name)]

    # --- dispatch -----------------------------------------------------------

    def dispatch(self, call: ToolCall) -> ToolOutcome:
        handlers: dict[str, Callable[[ToolCall], ToolOutcome]] = {
            "get_entity": self._get_entity,
            "blast_radius": self._blast_radius,
            "read_logs": self._read_logs,
            "lookup_advisory": self._lookup_advisory,
            "related_incidents": self._related_incidents,
            "draft_detection_rule": self._draft_detection_rule,
            "what_if_we_had_acted": self._what_if_we_had_acted,
            "argue_the_other_side": self._argue_the_other_side,
        }
        if not self.spec.may_use(call.name):
            return ToolOutcome(
                call=call,
                ok=False,
                content=f"{call.name!r} is not available to this agent.",
                refused="not declared",
            )
        handler = handlers.get(call.name)
        if handler is None:
            # The gateway refuses unoffered names before reaching here; this is
            # the second of the two locks, for the case where the offered list
            # and the handler table drift apart.
            return ToolOutcome(
                call=call,
                ok=False,
                content=f"No tool named {call.name!r}.",
                refused="no handler",
            )
        return handler(call)

    def _lookup_advisory(self, call: ToolCall) -> ToolOutcome:
        """One stored advisory, by identifier.

        Not routed through `_scoped`, and that is the point of it being its own
        handler. `_scoped` restricts lookups to this incident's entities because
        an open-ended entity lookup on a public console is an interface for
        asking which of *our* hosts and accounts exist. A CVE id is a public
        identifier for a public document, so the same restriction would buy
        nothing and would stop the agent answering the question R26 is about.

        The identifier is validated against the CVE pattern rather than passed
        through. Without that, the argument is an arbitrary string reaching
        `entity_events`, and `account:j.rivera` is an arbitrary string.
        """
        from . import context

        raw = str(call.arguments.get("identifier") or "").strip()
        found = context.identifiers(raw)
        if not found:
            return ToolOutcome(
                call=call,
                ok=False,
                content=(
                    f"{raw!r} is not a vulnerability identifier. This tool takes "
                    "a CVE id such as CVE-2026-0001 and nothing else."
                ),
                refused="not an identifier",
            )

        identifier = found[0]
        rows = self.graph.entity_events(f"vulnerability:{identifier}", limit=1)
        if not rows:
            return ToolOutcome(
                call=call,
                ok=True,
                content=(
                    f"No stored advisory for {identifier}. Nothing has been "
                    "ingested for it, so there is nothing here to answer from."
                ),
            )

        row = rows[0]
        return ToolOutcome(
            call=call,
            ok=True,
            content="\n".join(context._advisory_lines(identifier, row)),
            # The ref is what makes the answer citable. Without it the model can
            # read the advisory and then have nothing that resolves to cite.
            refs=[row["id"]],
        )

    def _related_incidents(self, call: ToolCall) -> ToolOutcome:
        """Is that one the same story as this one? (R69)

        Deterministic, and not routed through `_scoped`. The entity scope exists
        because an open-ended entity lookup on a public console is a way to ask
        which of *our* hosts and accounts exist; an incident id is already
        listed on `/incidents`, so naming one buys an attacker nothing it did
        not have. The store's own `get` is the boundary — an id that is not an
        incident is refused rather than compared against nothing.

        The judgement is `relate`'s and no part of it is the model's. What comes
        back is a sentence and a list of refs, and the refs are what make either
        answer checkable: a relation names the records on both sides, and a "no"
        names what was compared.
        """
        from pashupatastra.relations import relate

        other_id = str(call.arguments.get("incident_id") or "").strip()
        if not other_id:
            return ToolOutcome(
                call=call,
                ok=False,
                content="incident_id is required — the other incident to compare against.",
                refused="missing argument",
            )
        if other_id == self.incident.id:
            return ToolOutcome(
                call=call,
                ok=False,
                content=(
                    f"{other_id} is the incident under discussion. Compare it "
                    "against a different one."
                ),
                refused="same incident",
            )
        other = self.store.get(other_id) if self.store is not None else None
        if other is None:
            return ToolOutcome(
                call=call,
                ok=False,
                content=f"No incident {other_id!r} is stored.",
                refused="not found",
            )

        relation = relate(self.incident, other)
        return ToolOutcome(
            call=call,
            ok=True,
            content=relation.describe(),
            # Empty on a "no", deliberately. There is nothing to cite for an
            # absence, and handing back refs anyway would let an answer that
            # found no relation still look sourced.
            refs=relation.refs,
        )

    def _draft_detection_rule(self, call: ToolCall) -> ToolOutcome:
        """Draft a Sigma rule for one step of this incident (R71).

        Deterministic like `related_incidents`, and for the same reason. Which
        telemetry field corresponds to which Sigma field is a fact about our
        event model, not a judgement, and a model asked to make the mapping
        would produce `EventID: 5145` — the shape such rules have — from a store
        that holds no Windows event ids at all.

        **The rule text is deliberately not returned.** What comes back is the
        mapping table and the gaps; the YAML is served by
        `/incidents/{id}/detection-rule/{technique}` and rendered on the page.
        Two reasons, and the second is the important one:

        - A Sigma rule is several hundred tokens, and answers here are bounded
          at 800 against a per-minute allowance (R19).
        - A model that retypes a machine-readable artefact will eventually
          retype it wrong, and one dropped character is a rule that does not
          parse. Nothing in the loop could catch it: the model cannot re-read
          what it just emitted, and the reader sees a rule that looks fine.
          An artefact should reach a reader by the path that generated it.

        Scoped to this incident's own techniques. The argument is checked
        against the causal chain rather than passed through, so this cannot be
        used to ask the console about a technique the incident never carried.
        """
        from pashupatastra.sigma import SigmaError, draft_rule, rule_techniques

        raw = str(call.arguments.get("technique_id") or "").strip()
        available = rule_techniques(self.incident)
        if not available:
            return ToolOutcome(
                call=call,
                ok=True,
                content=(
                    f"{self.incident.id} has no causal step carrying an attack "
                    "technique, so there is no adversary behaviour here to write a "
                    "detection rule for."
                ),
            )

        names = ", ".join(f"{t.id} ({t.name})" for t in available)
        if not raw:
            return ToolOutcome(
                call=call,
                ok=False,
                content=f"technique_id is required. This incident carries: {names}.",
                refused="missing argument",
            )
        if raw not in {t.id for t in available}:
            return ToolOutcome(
                call=call,
                ok=False,
                content=f"{raw} is not a technique in this incident. It carries: {names}.",
                refused="not in this incident",
            )

        from ..graph import events_by_id

        cited = [
            ref
            for link in self.incident.causal_chain
            if link.attack_technique is not None and link.attack_technique.id == raw
            for ref in link.evidence
        ]
        events = events_by_id(self.graph, cited)

        try:
            rule = draft_rule(self.incident, events, raw)
        except SigmaError as exc:
            # A refusal is an answer here, not a failure. "This step's telemetry
            # carries no field Sigma has a name for" is the honest result and
            # the model should report it rather than trying another technique.
            return ToolOutcome(call=call, ok=True, content=str(exc), refs=cited)

        lines = [
            (
                f"Drafted a Sigma rule for {rule.technique.id} ({rule.technique.name}) "
                f"from {rule.incident_ref}. It is shown on the incident page; do not "
                "retype it."
            ),
            "",
            "Telemetry field -> Sigma field:",
        ]
        lines += [f"  {m.describe()}" for m in rule.mappings]
        if rule.gaps:
            lines += ["", "Fields this telemetry could not supply:"]
            lines += [f"  {g.sigma_field}: {g.reason}" for g in rule.gaps]
        if rule.unmapped:
            lines += ["", "Held and deliberately not mapped:"]
            lines += [f"  {g.sigma_field}: {g.reason}" for g in rule.unmapped]
        if not rule.behavioural:
            lines += [
                "",
                (
                    "Every field is an instance value from this incident, so this would "
                    "have matched this occurrence and will not match another. It is an "
                    "indicator match rather than a detection for the technique, and "
                    "that is stated in the rule itself."
                ),
            ]
        return ToolOutcome(call=call, ok=True, content="\n".join(lines), refs=rule.refs)

    def _what_if_we_had_acted(self, call: ToolCall) -> ToolOutcome:
        """What acting earlier would have prevented (R72).

        Deterministic, like the two tools before it. "How much of this would not
        have happened" is a walk over a stored timeline and stored access edges,
        and a model asked to estimate it produces a plausible number nobody can
        check — on the one question where a plausible number is most likely to
        be repeated in a slide.

        The moment defaults to the earliest the records would have justified
        acting. That is both the interesting question — it is what the
        homepage's cost-of-the-gap framing is about — and the one a model can
        ask without inventing a timestamp, which it would otherwise place before
        anything was observed and get a refusal it would read as a broken tool.
        """
        from datetime import datetime

        from pashupatastra.counterfactual import (
            CounterfactualRefused,
            Intervention,
            counterfactual,
            earliest_defensible,
            moments,
        )

        from ..graph import chain_times

        key = str(call.arguments.get("entity_key") or "").strip()
        chain_entities = {link.entity.key() for link in self.incident.causal_chain}
        if not key:
            return ToolOutcome(
                call=call,
                ok=False,
                content="entity_key is required. Give one of: "
                + ", ".join(sorted(chain_entities)),
                refused="missing argument",
            )
        if key not in chain_entities:
            return ToolOutcome(
                call=call,
                ok=False,
                content=(
                    f"{key} is not on this incident's causal chain. Entities on it: "
                    + ", ".join(sorted(chain_entities))
                ),
                refused="not on the chain",
            )

        observed = chain_times(self.graph, self.incident)
        timeline = moments(self.incident, observed)
        if not timeline:
            return ToolOutcome(
                call=call,
                ok=True,
                content=(
                    f"No step of {self.incident.id} resolves to a stored event, so there "
                    "is no timeline to reason about and no 'earlier' to estimate against."
                ),
            )

        raw = str(call.arguments.get("at") or "").strip()
        if raw:
            try:
                moment = datetime.fromisoformat(raw)
            except ValueError:
                return ToolOutcome(
                    call=call,
                    ok=False,
                    content=f"{raw!r} is not an ISO timestamp.",
                    refused="bad timestamp",
                )
        else:
            moment = earliest_defensible(self.incident, key, observed)
            if moment is None:
                return ToolOutcome(
                    call=call,
                    ok=True,
                    content=(
                        f"Nothing stored places {key} in time, so there is no moment "
                        "from which acting on it would have been possible."
                    ),
                )

        reach = self.topology.blast_radius(key).affected
        try:
            result = counterfactual(
                self.incident, Intervention(entity_key=key, at=moment), observed, reach
            )
        except CounterfactualRefused as exc:
            # A refusal is the answer, not a failure. Most often it is the
            # clairvoyance rule, and the model reporting *that* is more valuable
            # than any number it could have been given instead.
            return ToolOutcome(call=call, ok=True, content=str(exc))

        lines = [result.describe(), "", "This estimate rests on:"]
        lines += [f"  - {line}" for line in result.basis]
        if result.untimed:
            lines += ["", "Steps that could not be placed in time:"]
            lines += [f"  - {u.entity_key}: {u.reason}" for u in result.untimed]
        return ToolOutcome(call=call, ok=True, content="\n".join(lines), refs=result.refs)

    def _argue_the_other_side(self, call: ToolCall) -> ToolOutcome:
        """The rival explanation's case, and what answers it (R73).

        Deterministic, and this is the tool where that matters most. Asked to
        argue against a diagnosis, a model will produce a fluent counterargument
        and then a fluent rebuttal of it, because that is a shape it can always
        write — and the result reads exactly like reasoning while resting on
        nothing. Worse, it will almost always conclude that the diagnosis
        survives, because agreeing with the material in front of it is the
        likelier continuation. A challenge that cannot come out the other way is
        not a challenge.

        So the verdict is computed from the records: the rival is beaten only
        where something stored and resolvable contradicts it, and the confidence
        gap never counts. What the model does with this is report it.
        """
        from pashupatastra.contest import ContestRefused, contest

        claimed = {
            ref
            for hypothesis in self.incident.hypotheses
            for ref in (*hypothesis.evidence, *hypothesis.contradicted_by)
        }
        resolvable = (
            {ref for ref in claimed if self.graph.event(ref) is not None}
            if self.graph is not None
            else set()
        )

        try:
            result = contest(self.incident, resolvable)
        except ContestRefused as exc:
            # A refusal is the answer. An incident with one hypothesis has no
            # other side, and inventing one to knock down would be the failure
            # rule 6 already forbids.
            return ToolOutcome(call=call, ok=True, content=str(exc))

        lines = [result.describe()]
        if result.verdict.value == "unrefuted":
            lines += [
                "",
                (
                    "Report this as an open question rather than as the alternative "
                    "being correct: it says the diagnosis has not earned its place "
                    "over the alternative, not that the alternative is right."
                ),
            ]
        if result.rival.uncited or result.leader.uncited:
            lines += [
                "",
                (
                    f"Evidence claimed and not resolvable: diagnosis "
                    f"{list(result.leader.uncited)}, alternative "
                    f"{list(result.rival.uncited)}."
                ),
            ]
        return ToolOutcome(call=call, ok=True, content="\n".join(lines), refs=result.refs)

    def _scoped(self, call: ToolCall) -> tuple[str | None, ToolOutcome | None]:
        key = str(call.arguments.get("entity_key") or "").strip()
        if not key:
            return None, ToolOutcome(
                call=call,
                ok=False,
                content="entity_key is required. Give one of: "
                + ", ".join(sorted(self._scope)),
                refused="missing argument",
            )
        if key not in self._scope:
            return None, ToolOutcome(
                call=call,
                ok=False,
                content=(
                    f"{key} is not part of this incident. Entities in scope: "
                    + ", ".join(sorted(self._scope))
                ),
                refused="out of scope",
            )
        return key, None

    def _get_entity(self, call: ToolCall) -> ToolOutcome:
        key, refusal = self._scoped(call)
        if refusal is not None:
            return refusal
        row = self.graph.entity(key)
        if row is None:
            return ToolOutcome(
                call=call, ok=False, content=f"No record for {key}.", refused="not found"
            )
        return ToolOutcome(call=call, ok=True, content=json.dumps(row, default=str), refs=[key])

    def _blast_radius(self, call: ToolCall) -> ToolOutcome:
        key, refusal = self._scoped(call)
        if refusal is not None:
            return refusal
        radius = self.topology.blast_radius(key)
        return ToolOutcome(
            call=call,
            ok=True,
            content=json.dumps(radius.model_dump(mode="json"), default=str),
            refs=[key],
        )

    def _read_logs(self, call: ToolCall) -> ToolOutcome:
        key, refusal = self._scoped(call)
        if refusal is not None:
            return refusal
        rows = self.graph.entity_events(key, limit=MAX_ROWS)
        if not rows:
            return ToolOutcome(call=call, ok=True, content=f"No events recorded for {key}.")
        lines, refs = [], []
        for row in rows:
            payload = row.get("payload") or {}
            summary = payload.get("message") or payload.get("summary") or ""
            lines.append(
                f"{row.get('occurred_at')} {row.get('event_class')} "
                f"severity={row.get('severity')} {summary}".strip()
            )
            refs.append(row["id"])
        return ToolOutcome(call=call, ok=True, content="\n".join(lines), refs=refs)
