"""The PIB schema, its validator, and the corpus itself.

Most of these feed the validator scenarios that are *wrong* in a specific way.
Each mistake here is one somebody makes while authoring a hundred files, is
invisible reading that file alone, and silently changes what the benchmark
measures — which makes rejecting them the validator's entire job.
"""

from __future__ import annotations

import pytest

from pashupatastra.pib import (
    SEED_CATEGORIES,
    Outcome,
    ScenarioError,
    load_corpus,
    load_scenario,
    report,
)

CORPUS = "benchmark/incidents/pib"


def a_scenario(**overrides) -> dict:
    base = {
        "scenario": {
            "id": "PIB-9001",
            "name": "test",
            "category": "database",
            "difficulty": "medium",
            "outcome": "remediate",
        },
        "setup": {"stack": "reference-5svc", "fault": {"type": "deployment", "detail": "x"}},
        "expected": {
            "root_cause": "something",
            "causal_chain": ["a", "b"],
            "action": "rollback_deployment",
            "recovery_state": {"error_rate": "<1%"},
        },
        "constraints": {
            "allowed_actions": ["rollback_deployment"],
            "forbidden_actions": ["delete_infrastructure"],
            "risk_ceiling": 60,
        },
    }
    for section, values in overrides.items():
        base.setdefault(section, {})
        if values is None:
            base[section] = {}
        else:
            base[section].update(values)
    return base


# --- the answer key must not contradict the constraints -----------------------


def test_an_expected_action_outside_its_own_allow_list_is_rejected() -> None:
    """The scenario would mark the correct answer as a false remediation, so the
    only way to score well is to get it wrong."""
    data = a_scenario(constraints={"allowed_actions": ["scale_service"]})
    with pytest.raises(ScenarioError, match="not in its own"):
        load_scenario(data)


def test_an_expected_action_that_is_also_forbidden_is_rejected() -> None:
    data = a_scenario(
        constraints={
            "allowed_actions": ["rollback_deployment"],
            "forbidden_actions": ["rollback_deployment"],
        }
    )
    with pytest.raises(ScenarioError, match="both allowed and forbidden"):
        load_scenario(data)


def test_an_action_in_both_lists_is_rejected_before_anything_else() -> None:
    """The grader would count the same action as correct and as a violation."""
    data = a_scenario(
        constraints={
            "allowed_actions": ["rollback_deployment", "scale_service"],
            "forbidden_actions": ["scale_service"],
        }
    )
    with pytest.raises(ScenarioError, match="both allowed and forbidden"):
        load_scenario(data)


# --- negative and escalation cases are the point ------------------------------


def test_a_negative_scenario_expecting_an_action_is_rejected() -> None:
    """The failure that would quietly undo the category: a negative case carrying
    an expected action scores a system that *acted* as correct, rewarding exactly
    the behaviour negatives exist to penalise."""
    data = a_scenario(
        scenario={"outcome": "nothing"},
        expected={"root_cause": None, "action": "restart_service"},
    )
    with pytest.raises(ScenarioError, match="correct answer is silence"):
        load_scenario(data)


def test_a_negative_scenario_with_a_root_cause_is_rejected() -> None:
    data = a_scenario(
        scenario={"outcome": "nothing"},
        expected={"action": None, "root_cause": "something"},
    )
    with pytest.raises(ScenarioError, match="no root cause"):
        load_scenario(data)


def test_an_escalation_scenario_expecting_a_remediation_is_rejected() -> None:
    data = a_scenario(
        scenario={"outcome": "escalate"},
        expected={"escalation_reason": "human call", "action": "restart_service"},
    )
    with pytest.raises(ScenarioError, match="handing off is the correct answer"):
        load_scenario(data)


def test_an_escalation_without_a_stated_reason_is_rejected() -> None:
    """Otherwise the grader cannot tell a correct hand-off from a system that
    simply gave up, and those deserve opposite scores."""
    data = a_scenario(
        scenario={"outcome": "escalate"},
        expected={"action": None, "root_cause": None, "escalation_reason": None},
    )
    with pytest.raises(ScenarioError, match="must say why it escalates"):
        load_scenario(data)


# --- a remediate scenario must be scoreable -----------------------------------


def test_a_remediate_scenario_without_a_recovery_state_is_rejected() -> None:
    """Without it, "did it work?" has no answer and the run cannot be graded."""
    data = a_scenario(expected={"recovery_state": {}})
    with pytest.raises(ScenarioError, match="recovery state"):
        load_scenario(data)


def test_a_remediate_scenario_without_a_root_cause_is_rejected() -> None:
    data = a_scenario(expected={"root_cause": None})
    with pytest.raises(ScenarioError, match="must state its root cause"):
        load_scenario(data)


def test_a_remediate_scenario_without_an_action_is_rejected() -> None:
    data = a_scenario(expected={"action": None})
    with pytest.raises(ScenarioError, match="must state the correct action"):
        load_scenario(data)


# --- structural ---------------------------------------------------------------


def test_a_category_outside_the_eight_seeds_is_rejected() -> None:
    """A ninth category silently creates a bucket nothing else covers."""
    data = a_scenario(scenario={"category": "miscellaneous"})
    with pytest.raises(ScenarioError, match="seed categories"):
        load_scenario(data)


def test_an_unknown_outcome_is_rejected() -> None:
    data = a_scenario(scenario={"outcome": "probably_fine"})
    with pytest.raises(ScenarioError):
        load_scenario(data)


def test_a_missing_required_field_names_the_field_and_the_file() -> None:
    data = a_scenario()
    del data["setup"]["stack"]
    with pytest.raises(ScenarioError, match="stack"):
        load_scenario(data, "PIB-0001.yaml")


def test_a_risk_ceiling_outside_the_scale_is_rejected() -> None:
    data = a_scenario(constraints={"risk_ceiling": 140})
    with pytest.raises(ScenarioError, match="outside 0"):
        load_scenario(data)


def test_a_valid_scenario_round_trips() -> None:
    s = load_scenario(a_scenario())
    assert s.id == "PIB-9001"
    assert s.outcome is Outcome.REMEDIATE
    assert s.expected.action == "rollback_deployment"
    assert not s.is_negative


# --- the corpus ---------------------------------------------------------------


def test_the_whole_corpus_validates() -> None:
    assert len(load_corpus(CORPUS)) >= 100


def test_the_corpus_has_at_least_a_hundred_scenarios() -> None:
    assert report(load_corpus(CORPUS)).total >= 100


def test_every_seed_category_is_covered() -> None:
    assert report(load_corpus(CORPUS)).uncovered_categories == []


def test_every_category_has_a_negative_case() -> None:
    """Aggregate counts hide this. A corpus with all its negatives in one
    category has negatives on paper and blind spots in the other seven."""
    assert report(load_corpus(CORPUS)).categories_without(Outcome.NOTHING) == []


def test_every_category_has_an_escalation_case() -> None:
    assert report(load_corpus(CORPUS)).categories_without(Outcome.ESCALATE) == []


def test_negatives_and_escalations_are_a_meaningful_share() -> None:
    """A token few would let a system that always acts still score well."""
    result = report(load_corpus(CORPUS))
    assert result.negatives >= 20
    assert result.escalations >= 15


def test_scenario_ids_are_unique() -> None:
    scenarios = load_corpus(CORPUS)
    assert len({s.id for s in scenarios}) == len(scenarios)


def test_the_corpus_spans_every_difficulty() -> None:
    by_difficulty = report(load_corpus(CORPUS)).by_difficulty
    assert set(by_difficulty) == {"easy", "medium", "hard"}


def test_no_scenario_permits_an_irreversible_action() -> None:
    """`delete_infrastructure` is denied by Dharma regardless. A scenario that
    allowed it would be authoring a test for a path that cannot execute."""
    for s in load_corpus(CORPUS):
        assert "delete_infrastructure" not in s.constraints.allowed_actions


def test_every_expected_action_is_a_registered_action() -> None:
    """An answer key naming an action that does not exist can never be matched."""
    from pashupatastra.registry import all_actions

    known = {a.id for a in all_actions()}
    for s in load_corpus(CORPUS):
        if s.expected.action:
            assert s.expected.action in known, f"{s.id} expects unknown {s.expected.action}"


def test_every_allowed_action_is_a_registered_action() -> None:
    from pashupatastra.registry import all_actions

    known = {a.id for a in all_actions()}
    for s in load_corpus(CORPUS):
        for action in s.constraints.allowed_actions:
            assert action in known, f"{s.id} allows unknown {action}"


def test_the_report_names_uncovered_categories_rather_than_a_bare_count() -> None:
    result = report([s for s in load_corpus(CORPUS) if s.category == "database"])
    missing = result.uncovered_categories
    assert "cache" in missing
    assert "database" not in missing
    assert len(missing) == len(SEED_CATEGORIES) - 1
