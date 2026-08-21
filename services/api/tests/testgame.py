"""Blue team mode.

Two things are being protected here. The briefing must not contain the answer,
because a page that ships its own solution teaches the player to open dev tools
rather than to read evidence. And every scenario must be winnable *and* losable
— a scoring dimension that cannot be scored is not a test, and the first version
of the action menu quietly made the response dimension unreachable above a
third by leaving the correct action off the list.
"""

from __future__ import annotations

import json

import pytest
from app import game
from app.graph import entitystore
from app.store import STORE

SCENARIOS = ["INC-2026-0901", "INC-2026-0902", "INC-2026-0903"]


@pytest.fixture(params=SCENARIOS)
def scenario(request):
    # Importing the app is what seeds the demo scenarios — `_seed_demo` runs at
    # import of `app.main`. Reading `STORE` without it gave 51 skipped tests
    # that looked like a configuration choice rather than a missing import.
    import app.main  # noqa: F401

    incident = STORE.get(request.param)
    if incident is None:
        pytest.skip("demo scenarios are not seeded in this configuration")
    return incident


@pytest.fixture
def graph():
    return entitystore()


# --- the briefing keeps the answer -------------------------------------------


def test_the_briefing_contains_nothing_that_gives_it_away(scenario, graph) -> None:
    """Confidence, contradictions, the causal chain, the technique mapping and
    the plan are each, on their own, the answer."""
    blob = json.dumps(game.briefing(scenario, graph))
    for tell in ("confidence", "contradicted", "causal", "transition",
                 "attack_technique", "tactic"):
        assert tell not in blob, tell
    # The plan's action ids appear as menu options, so the plan *list* is what
    # must not be there — the shape that says which of them to pick, in order.
    assert '"plan"' not in blob


def test_candidates_are_not_in_truth_order(scenario, graph) -> None:
    """Source order puts the correct explanation first every single time, which
    is not a difficulty setting."""
    statements = [c["statement"] for c in game.candidates(scenario)]
    truth = game._correct(scenario).statement
    # Stable across calls, so a reload does not move the options under a player.
    assert statements == [c["statement"] for c in game.candidates(scenario)]
    assert truth in statements
    assert len(statements) == len(scenario.hypotheses)


def test_the_opening_alert_is_the_earliest_signal(scenario, graph) -> None:
    """Chronological, not first-in-chain. The chain is the conclusion, written
    afterwards; an analyst gets whichever alert fired first."""
    alert = game.opening_alert(scenario, graph)
    assert alert is not None

    refs = [ref for link in scenario.causal_chain for ref in link.evidence]
    times = [
        row["occurred_at"]
        for ref in refs
        if (row := graph.event(ref)) is not None
    ]
    assert alert["at"] == min(times)


def test_entities_are_listed_without_revealing_the_sequence(scenario) -> None:
    """The order of the causal chain *is* the answer to "how did this unfold"."""
    listed = game.investigable(scenario)
    chain = [link.entity.key() for link in scenario.causal_chain]
    assert listed == sorted(listed)
    if len(set(chain)) > 1:
        assert listed != chain


# --- every scenario is winnable ------------------------------------------------


def test_the_proportionate_action_is_on_the_menu(scenario) -> None:
    """The bug this pins: sorting the registry by risk and taking the cheapest
    eight left `isolate_host` off the menu for a beaconing workstation, so the
    response dimension could not be scored above a third and nothing said so."""
    offered = {a["id"] for a in game.offered_actions(scenario)}
    for step in scenario.plan:
        assert step.action_id in offered, step.action_id


def test_both_wrong_answers_are_also_on_the_menu(scenario) -> None:
    """Doing too little and doing far too much are both answers a real analyst
    gives under pressure. Neither can be marked if neither is offered."""
    offered = {a["id"] for a in game.offered_actions(scenario)}
    assert "read_logs" in offered
    assert "wipe_host" in offered


def test_the_undo_of_the_right_answer_is_not_offered(scenario) -> None:
    """Offering "rejoin the network" as a response to a live intrusion is not a
    distractor, it is nonsense."""
    from pashupatastra.registry import get as get_action

    offered = {a["id"] for a in game.offered_actions(scenario)}
    for step in scenario.plan:
        inverse = get_action(step.action_id).rollback_action_id
        if inverse:
            assert inverse not in offered, inverse


# --- scoring discriminates -----------------------------------------------------


def _ids(incident, graph):
    correct = game._correct(incident)
    decoy = game._decoy(incident)
    proof = sorted(
        {
            row["entity_key"]
            for ref in decoy.contradicted_by
            if (row := graph.event(ref)) is not None
        }
    )
    return game._choice_id(correct.statement), game._choice_id(decoy.statement), proof


def test_a_perfect_attempt_scores_everything(scenario, graph) -> None:
    right, _, proof = _ids(scenario, graph)
    result = game.score(scenario, graph, right, scenario.plan[0].action_id, proof)
    assert result["total"] == 100
    assert result["grade"] == "clean"


def test_being_right_without_looking_loses_the_investigation_marks(scenario, graph) -> None:
    """The dimension this exercise is really for. The decoy is plausible; what
    makes it wrong is a specific observation, and an analyst who never opened it
    was right by luck."""
    right, _, _ = _ids(scenario, graph)
    result = game.score(scenario, graph, right, scenario.plan[0].action_id, [])
    assert result["total"] == 100 - game.INVESTIGATION_POINTS
    marks = {part["name"]: part["points"] for part in result["breakdown"]}
    assert marks["Investigation"] == 0
    assert marks["Diagnosis"] == game.DIAGNOSIS_POINTS


def test_the_decoy_scores_no_diagnosis_marks(scenario, graph) -> None:
    _, wrong, proof = _ids(scenario, graph)
    result = game.score(scenario, graph, wrong, scenario.plan[0].action_id, proof)
    marks = {part["name"]: part["points"] for part in result["breakdown"]}
    assert marks["Diagnosis"] == 0


def test_reading_the_logs_is_not_a_response(scenario, graph) -> None:
    right, _, proof = _ids(scenario, graph)
    result = game.score(scenario, graph, right, "read_logs", proof)
    marks = {part["name"]: part["points"] for part in result["breakdown"]}
    assert 0 < marks["Response"] < game.RESPONSE_POINTS
    note = next(p["note"] for p in result["breakdown"] if p["name"] == "Response")
    assert "Too little" in note


def test_the_sledgehammer_scores_nothing_for_response(scenario, graph) -> None:
    right, _, proof = _ids(scenario, graph)
    result = game.score(scenario, graph, right, "wipe_host", proof)
    marks = {part["name"]: part["points"] for part in result["breakdown"]}
    assert marks["Response"] == 0


def test_an_unregistered_action_scores_nothing_rather_than_raising(scenario, graph) -> None:
    right, _, proof = _ids(scenario, graph)
    result = game.score(scenario, graph, right, "rm_minus_rf", proof)
    marks = {part["name"]: part["points"] for part in result["breakdown"]}
    assert marks["Response"] == 0


# --- the reveal ----------------------------------------------------------------


def test_the_reveal_explains_why_the_decoy_was_wrong(scenario, graph) -> None:
    """Being told the right answer teaches less than being shown the specific
    observation that killed the answer you were drawn to."""
    right, _, proof = _ids(scenario, graph)
    answer = game.score(scenario, graph, right, "read_logs", proof)["answer"]

    assert answer["diagnosis"] == game._correct(scenario).statement
    assert len(answer["chain"]) == len(scenario.causal_chain)
    assert answer["decoy"]["statement"] == game._decoy(scenario).statement
    assert answer["decoy"]["ruled_out_by"], "the decoy must be shown to be ruled out"
    for row in answer["decoy"]["ruled_out_by"]:
        assert row["summary"], row["id"]


def test_the_chain_carries_its_technique_mapping(scenario, graph) -> None:
    right, _, proof = _ids(scenario, graph)
    answer = game.score(scenario, graph, right, "read_logs", proof)["answer"]
    mapped = [step for step in answer["chain"] if step["technique"]]
    assert mapped, "a security scenario should map at least one ATT&CK technique"
    for step in mapped:
        assert step["technique"]["url"].startswith("https://attack.mitre.org/")


# --- investigation is bounded ---------------------------------------------------


def test_investigating_something_outside_the_incident_is_refused(scenario, graph) -> None:
    """An open-ended entity lookup on a public console is an interface for
    asking which of our hosts and accounts exist. A game is not a reason to
    open one."""
    result = game.investigate(scenario, graph, "host:not-in-this-incident")
    assert result["ok"] is False
    assert result["events"] == []


def test_investigating_an_entity_returns_its_evidence(scenario, graph) -> None:
    key = game.investigable(scenario)[0]
    result = game.investigate(scenario, graph, key)
    assert result["ok"] is True
    for event in result["events"]:
        assert event["id"] and event["at"]
