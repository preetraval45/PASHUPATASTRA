"""Blue team progress, and the promise that it collects nothing about anyone.

The scoring rules are pure functions and are tested as such. The privacy
properties are tested too, because they are claims — "we hold no personal data",
"there is no leaderboard" — and a claim nobody asserts is a comment.
"""

from __future__ import annotations

import uuid

from app import progress


def token() -> str:
    return str(uuid.uuid4())


# --- the identifier -----------------------------------------------------------


def test_only_a_uuid_is_accepted_as_a_player() -> None:
    """The shape is what makes "we hold no personal data" structural rather
    than aspirational. Without it the identifier is an arbitrary string that
    becomes a sort key, and it would store `alice@example.com` quite happily
    the first time somebody sent one."""
    assert progress.valid(token())
    for rejected in (
        "alice@example.com",
        "alice",
        "",
        None,
        "../../etc/passwd",
        "0000",
        str(uuid.uuid4()).upper(),  # canonical lowercase only
        str(uuid.uuid4()) + "x",
    ):
        assert not progress.valid(rejected), rejected


def test_there_is_no_route_that_lists_players() -> None:
    """The absence is the feature. An enumerable set of scores is a
    leaderboard, and a leaderboard is what this was asked not to be."""
    from app.api import routes

    paths = [route.path for route in routes.router.routes]
    assert "/game/progress/{player_id}" in paths
    assert not any(
        path.rstrip("/").endswith("/players") or path.rstrip("/").endswith("/leaderboard")
        for path in paths
    )


def test_a_malformed_token_is_ignored_rather_than_fatal() -> None:
    """A bad token is a client bug or a probe. Neither is a reason to fail the
    attempt somebody just spent five minutes on."""
    store = progress.Progress(resolver=lambda: None)
    assert store.add("not-a-token", "INC-1", 100) == progress.empty()
    assert store.get("not-a-token") == progress.empty()


# --- the rules -----------------------------------------------------------------


def test_a_streak_counts_sound_results_and_breaks_on_a_bad_one() -> None:
    """A streak that survives a wrong diagnosis measures persistence, not
    competence."""
    state = None
    for total in (100, 80, 70):
        state = progress.record(state, "INC-1", total)
    assert state["streak"] == 3

    state = progress.record(state, "INC-1", 69)
    assert state["streak"] == 0
    assert state["best_streak"] == 3


def test_the_best_score_never_goes_down() -> None:
    """A player who scores 100 and then experiments with a deliberately wrong
    answer has not got worse at it."""
    state = progress.record(None, "INC-1", 100)
    state = progress.record(state, "INC-1", 0)
    assert state["best"]["INC-1"] == 100
    assert state["attempts"] == 2


def test_only_a_clean_run_clears_a_scenario() -> None:
    state = progress.record(None, "INC-1", progress.CLEAN - 1)
    assert state["cleared"] == []
    state = progress.record(state, "INC-1", progress.CLEAN)
    assert state["cleared"] == ["INC-1"]


def test_scenarios_are_tracked_separately() -> None:
    state = progress.record(None, "INC-1", 100)
    state = progress.record(state, "INC-2", 40)
    assert state["best"] == {"INC-1": 100, "INC-2": 40}
    assert state["cleared"] == ["INC-1"]


def test_recording_does_not_mutate_what_it_was_given() -> None:
    """`record` folds, it does not edit. A caller holding the previous state —
    which the durable path does, between a read and a write — must not find it
    changed underneath."""
    before = progress.record(None, "INC-1", 100)
    snapshot = {**before, "best": dict(before["best"]), "cleared": list(before["cleared"])}
    progress.record(before, "INC-2", 100)
    assert before == snapshot


# --- persistence ----------------------------------------------------------------


class FakeStore:
    """A durable backend, without a table."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def get_player(self, player_id: str) -> dict | None:
        return self.rows.get(player_id)

    def save_player(self, player_id: str, record: dict) -> None:
        # Stored with the columns the real one adds, so the read path is
        # exercised against the shape it will actually meet.
        self.rows[player_id] = {**record, "at": "2026-08-21T00:00:00+00:00"}


def test_a_score_survives_a_new_process() -> None:
    """R28's done-when. Two `Progress` objects sharing a backend and sharing no
    memory — which is what a Lambda cold start is."""
    backend = FakeStore()
    player = token()

    first = progress.Progress(resolver=lambda: backend)
    first.add(player, "INC-1", 100)

    second = progress.Progress(resolver=lambda: backend)
    assert second.get(player)["best"]["INC-1"] == 100
    assert second.get(player)["attempts"] == 1

    second.add(player, "INC-1", 80)
    assert progress.Progress(resolver=lambda: backend).get(player)["streak"] == 2


def test_the_storage_layers_own_columns_do_not_come_back() -> None:
    """A read path that returns rows as stored is how the namespace ended up on
    the public intel route."""
    backend = FakeStore()
    player = token()
    store = progress.Progress(resolver=lambda: backend)
    store.add(player, "INC-1", 100)

    assert set(store.get(player)) == {"attempts", "streak", "best_streak", "cleared", "best"}


def test_without_a_backend_it_still_works_within_the_process() -> None:
    store = progress.Progress(resolver=lambda: None)
    player = token()
    store.add(player, "INC-1", 100)
    assert store.get(player)["best"]["INC-1"] == 100
    assert store.durable is False


# --- the score comes from the server ---------------------------------------------


def test_the_client_cannot_post_its_own_score() -> None:
    """A number a player can choose is not a score. The request model carries
    choices and a token, and nothing that looks like a total."""
    from app.api.routes import AnswerRequest

    fields = set(AnswerRequest.model_fields)
    assert fields == {"diagnosis_id", "action_id", "investigated", "player_id"}
    for forbidden in ("total", "score", "grade", "points"):
        assert forbidden not in fields


def test_the_audit_line_does_not_carry_the_token(monkeypatch) -> None:
    """The trail is public. A pseudonymous id printed beside a timestamp on a
    public page is a thing that can be correlated."""
    import inspect

    from app.api import routes

    source = inspect.getsource(routes.game_answer)
    summary = source[source.index("AuditRecord(") : source.index("PROGRESS.add")]
    assert "player_id" not in summary
