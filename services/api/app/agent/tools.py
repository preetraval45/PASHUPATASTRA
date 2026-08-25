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
    ) -> None:
        from .roles import ANALYST

        self.incident = incident
        self.store = store
        self.graph = graph
        self.domain = domain
        self.spec = spec or ANALYST
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
        radius = self.graph.blast_radius(key)
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
