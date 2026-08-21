"""What a player has done, kept between visits.

**Anonymous by default, and that is a decision about data rather than about
features.** A leaderboard with names is a system that collects names: it needs a
retention answer, a deletion path, a moderation policy for what people type in,
and a line in a privacy notice. None of that is worth acquiring so a training
exercise can say "well done".

So there is no name and no account. The browser generates an opaque token, keeps
it locally, and sends it with an attempt. The server can tell that two attempts
came from the same browser and nothing else — not who, not where, not whether
it is the same person. Clearing site data ends the association permanently,
because there is nothing else to join it to.

The token is still a persistent identifier and is treated as one: it is
validated to a fixed shape so it cannot carry a name someone typed, it is never
logged, and it is never returned in any list. There is no route that enumerates
players, which is what stops this being a leaderboard by accident.

**Scores are computed here, never accepted from the client.** The attempt route
receives choices and marks them; a client that posted its own total would be
posting a number, and a number a player can choose is not a score.
"""

from __future__ import annotations

import re
from typing import Any

TOKEN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
"""A UUID, and nothing else.

Not decoration. Without a shape, the identifier is an arbitrary string that
becomes a DynamoDB sort key — so it would happily store `alice@example.com` if
somebody sent it, and the "we hold no personal data" claim would be false the
first time anyone tried. A fixed shape makes the claim structural.
"""

KEEPS_STREAK = 70
"""A `sound` result or better. Below that the streak resets — a streak that
survives a wrong diagnosis is measuring persistence, not competence."""

CLEAN = 90


def valid(player_id: str | None) -> bool:
    return bool(player_id) and bool(TOKEN.match(player_id or ""))


def empty() -> dict[str, Any]:
    return {
        "attempts": 0,
        "streak": 0,
        "best_streak": 0,
        "cleared": [],
        "best": {},
    }


def record(existing: dict[str, Any] | None, incident_id: str, total: int) -> dict[str, Any]:
    """Fold one marked attempt into what was already there.

    Pure, and takes the previous state rather than reading it, so the rules are
    testable without a store and the same function serves the durable and the
    in-memory paths.
    """
    state = {**empty(), **(existing or {})}

    state["attempts"] = int(state["attempts"]) + 1

    best = dict(state["best"])
    # Best per scenario, not last: a player who scores 100 and then experiments
    # with a deliberately wrong answer has not got worse at it.
    best[incident_id] = max(int(best.get(incident_id, 0)), total)
    state["best"] = best

    if total >= KEEPS_STREAK:
        state["streak"] = int(state["streak"]) + 1
    else:
        state["streak"] = 0
    state["best_streak"] = max(int(state["best_streak"]), state["streak"])

    cleared = set(state["cleared"])
    if total >= CLEAN:
        cleared.add(incident_id)
    state["cleared"] = sorted(cleared)

    return state


class Progress:
    """Durable when a durable backend exists, in-process when it does not.

    Resolves the backend on each access through `backend.durable()` — the one
    resolver R18 established — rather than being handed a store. Being handed
    one is what left the answer cache bound on the first request a container
    served and not before, so `/health` could only ever report it unbound.
    """

    def __init__(self, resolver=None) -> None:
        self._resolver = resolver
        self._local: dict[str, dict] = {}

    @property
    def store(self):
        if self._resolver is not None:
            return self._resolver()
        from .backend import durable

        return durable()

    @property
    def durable(self) -> bool:
        return hasattr(self.store, "save_player")

    def get(self, player_id: str) -> dict[str, Any]:
        if not valid(player_id):
            return empty()
        store = self.store
        if hasattr(store, "get_player"):
            found = store.get_player(player_id)
            if found is not None:
                return {**empty(), **_clean(found)}
        return self._local.get(player_id, empty())

    def add(self, player_id: str, incident_id: str, total: int) -> dict[str, Any]:
        if not valid(player_id):
            # Silently ignored rather than refused. A malformed token is a
            # client bug or a probe, and neither is a reason to fail the attempt
            # a person just spent five minutes on.
            return empty()
        updated = record(self.get(player_id), incident_id, total)
        self._local[player_id] = updated
        store = self.store
        if hasattr(store, "save_player"):
            store.save_player(player_id, updated)
        return updated


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    """Drop the storage layer's own columns.

    `save_player` writes an `at` stamp beside the record, and the table adds
    `PK`/`SK`. None of that belongs in a response, and a read path that returns
    rows as stored is how the namespace ended up on the public intel route.
    """
    return {
        key: value
        for key, value in row.items()
        if key in {"attempts", "streak", "best_streak", "cleared", "best"}
    }


PROGRESS = Progress()
"""Process-wide, like the audit log, the store and the answer cache."""
