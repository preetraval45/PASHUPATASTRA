"""The labelled scenario corpus and its loader.

A corpus that silently loses its answer key still runs and still produces a
number, and that number is worse than none because it looks like a result. So
most of these tests are about the loader refusing malformed scenarios rather than
about the scenarios themselves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pashupatastra.detection import Finding
from pashupatastra.events import EventClass
from pashupatastra.scenarios import (
    Baseline,
    CorpusResult,
    Expectation,
    ScenarioResult,
    load_scenario,
    load_scenarios,
)

CORPUS = Path(__file__).resolve().parents[3] / "benchmark" / "incidents"


def a_definition(**overrides: object) -> dict:
    base = {
        "id": "SC-TEST",
        "name": "test",
        "category": "test",
        "expectation": "incident",
        "root_cause": "something broke",
        "signals": [{"at_seconds": 0, "entity": "service:a", "anomalous": True}],
    }
    return {**base, **overrides}


# --- the loader refuses malformed scenarios ----------------------------------


def test_a_missing_field_is_rejected() -> None:
    definition = a_definition()
    del definition["expectation"]
    with pytest.raises(ValueError, match="missing required field"):
        load_scenario(definition)


def test_an_incident_scenario_must_state_its_root_cause() -> None:
    """Otherwise there is nothing to be right about, and the scenario scores
    every answer as correct."""
    with pytest.raises(ValueError, match="root cause"):
        load_scenario(a_definition(root_cause=None))


def test_a_negative_scenario_must_not_state_a_root_cause() -> None:
    with pytest.raises(ValueError, match="must not state a root cause"):
        load_scenario(a_definition(expectation="nothing", root_cause="something"))


def test_an_incident_scenario_must_mark_its_anomalous_signals() -> None:
    """Without the answer key, detection cannot be scored — only asserted."""
    with pytest.raises(ValueError, match="mark which signals"):
        load_scenario(
            a_definition(signals=[{"at_seconds": 0, "entity": "service:a"}])
        )


def test_a_scenario_with_no_signals_tests_nothing() -> None:
    with pytest.raises(ValueError, match="tests nothing"):
        load_scenario(a_definition(expectation="nothing", root_cause=None, signals=[]))


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    for name in ("a.yaml", "b.yaml"):
        (tmp_path / name).write_text(
            "id: SAME\nname: x\ncategory: c\nexpectation: nothing\nsignals:\n"
            "  - {at_seconds: 0, entity: 'service:a'}\n",
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="duplicate scenario id"):
        load_scenarios(tmp_path)


# --- baselines ----------------------------------------------------------------


def test_a_baseline_expands_to_enough_samples_to_warm_a_detector() -> None:
    """The first version of this corpus gave each scenario four samples and every
    incident was missed — not a bug, but a detector correctly reporting UNKNOWN.
    A corpus that ignores warm-up measures a system nobody could deploy."""
    signals = Baseline(entity="service:a", name="m", value=1.0, samples=30).expand()
    assert len(signals) == 30
    assert not any(signal.anomalous for signal in signals)


def test_baseline_expansion_is_deterministic() -> None:
    """A corpus whose results change between runs is not a corpus."""
    spec = Baseline(entity="service:a", name="m", value=1.0, jitter=0.5)
    assert [s.value for s in spec.expand()] == [s.value for s in spec.expand()]


def test_drift_makes_a_ramp_rather_than_a_step() -> None:
    """A flat run with a jump at the end is not a ramp, and is legitimately
    anomalous — labelling one as benign would make the corpus wrong, not the
    detector."""
    values = [s.value for s in Baseline(
        entity="service:a", name="m", value=100.0, samples=10, jitter=0.0, drift=5.0
    ).expand()]
    assert values[0] == 100.0
    assert values[-1] == 145.0
    assert all(b > a for a, b in zip(values, values[1:]))


# --- replay -------------------------------------------------------------------


def test_scenarios_replay_at_a_fixed_epoch() -> None:
    """Times are offsets, so the corpus does not shift with the calendar."""
    scenario = load_scenario(a_definition())
    first = scenario.events()[0].occurred_at
    assert scenario.events()[0].occurred_at == first


def test_deployment_signals_become_deployment_events() -> None:
    scenario = load_scenario(
        a_definition(
            signals=[
                {"at_seconds": 0, "entity": "service:a", "kind": "deployment", "version": "v1"},
                {"at_seconds": 60, "entity": "service:a", "anomalous": True},
            ]
        )
    )
    classes = [event.event_class for event in scenario.events()]
    assert EventClass.DEPLOYMENT in classes


def test_the_answer_key_names_the_anomalous_events() -> None:
    scenario = load_scenario(
        a_definition(
            signals=[
                {"at_seconds": 0, "entity": "service:a"},
                {"at_seconds": 60, "entity": "service:a", "anomalous": True},
            ]
        )
    )
    assert scenario.anomalous_event_ids() == {"SC-TEST-001"}


def test_truth_falls_back_to_the_scenario_when_unlabelled() -> None:
    scenario = load_scenario(a_definition())
    finding = Finding(
        entity_key="service:unknown",
        signal="m",
        at=scenario.events()[0].occurred_at,
        value=1.0,
        baseline=0.0,
        deviation=3.0,
        direction="high",
        confidence=0.9,
        source="baseline",
    )
    assert scenario.truth_for(finding) == "SC-TEST"


# --- scoring reports failures first ------------------------------------------


def test_a_false_alarm_is_a_failure_even_though_nothing_was_missed() -> None:
    result = ScenarioResult(
        scenario_id="x",
        expectation=Expectation.NOTHING,
        detected=True,
        incidents_found=1,
        incidents_expected=0,
    )
    assert result.false_alarm
    assert not result.passed


def test_a_missed_incident_is_a_failure() -> None:
    result = ScenarioResult(
        scenario_id="x",
        expectation=Expectation.INCIDENT,
        detected=False,
        incidents_found=0,
        incidents_expected=1,
    )
    assert result.missed
    assert not result.passed


def test_a_false_precedent_fails_even_when_detection_was_right() -> None:
    """Claiming history that did not exist sends an operator confidently down a
    path that is not there."""
    result = ScenarioResult(
        scenario_id="x",
        expectation=Expectation.INCIDENT,
        detected=True,
        incidents_found=1,
        incidents_expected=1,
        precedent_found="INC-WRONG",
        precedent_expected=None,
    )
    assert not result.passed


def test_the_summary_leads_with_failures() -> None:
    """A summary that leads with a pass rate is read as a pass rate."""
    keys = list(CorpusResult().summary())
    assert keys.index("false_alarms") < keys.index("passed")
    assert keys.index("missed") < keys.index("passed")


# --- the shipped corpus -------------------------------------------------------


def test_the_shipped_corpus_loads() -> None:
    scenarios = load_scenarios(CORPUS)
    assert len(scenarios) >= 8


def test_the_corpus_contains_negative_cases() -> None:
    """Without them, a system that flags everything scores perfectly."""
    scenarios = load_scenarios(CORPUS)
    assert sum(1 for s in scenarios if s.expectation is Expectation.NOTHING) >= 2


def test_the_corpus_contains_an_escalation_case() -> None:
    """Without one, the corpus rewards guessing over handing off."""
    scenarios = load_scenarios(CORPUS)
    assert any(s.expectation is Expectation.ESCALATE for s in scenarios)


def test_the_corpus_contains_a_must_not_merge_case() -> None:
    """The failure mode correlation exists to prevent."""
    scenarios = load_scenarios(CORPUS)
    assert any(s.expected_incidents >= 2 for s in scenarios)


def test_every_scenario_explains_why_it_exists() -> None:
    """A scenario without a stated purpose is one nobody can judge the fairness
    of later — including whether it was written to be passed."""
    for scenario in load_scenarios(CORPUS):
        assert scenario.notes.strip(), f"{scenario.id} has no notes"
