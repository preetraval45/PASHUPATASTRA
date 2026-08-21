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
