"""The diagnosis grader, held to the properties the paper will quote.

Two of these are negative controls. A grader is the kind of code that passes
every test while being wrong in the direction that flatters the thing it
grades, so the suite checks that a wrong answer actually loses and that a
scenario with no answer key is not counted as a miss.
"""

from __future__ import annotations

import pytest

from pashupatastra.diagnosis import (
    LEAKAGE,
    Accuracy,
    chain_credit,
    choices,
    grade,
    labels,
    scoreable,
    summarise,
    wilson,
)
from pashupatastra.pib import load_corpus

CORPUS = load_corpus("benchmark/incidents/pib")


def test_the_corpus_carries_its_own_answer_key():
    scored = scoreable(CORPUS)
    assert len(scored) == 60
    # One label per scoreable scenario, all distinct: the task really is a
    # 60-way choice, not a handful of labels reused across scenarios.
    assert len(labels(CORPUS)) == len(scored)


def test_a_scenario_with_no_root_cause_is_excluded_not_failed():
    # The negative control that matters most. Twenty-five scenarios are correct
    # to do nothing about and nineteen to escalate; scoring those as diagnosis
    # misses would penalise an arm for being right, and would quietly drag any
    # reported accuracy toward a third of its true value.
    unscoreable = [s for s in CORPUS if not s.expected.root_cause]
    assert len(unscoreable) == 44
    for scenario in unscoreable:
        assert scenario not in scoreable(CORPUS)


def test_the_correct_label_is_always_among_the_options():
    for scenario in scoreable(CORPUS):
        for count in (0, 8, 4):
            offered = choices(scenario, CORPUS, count=count)
            assert scenario.expected.root_cause in offered


def test_a_narrowed_option_set_is_the_requested_size_and_category_matched():
    scenario = next(s for s in scoreable(CORPUS) if s.category == "database")
    offered = choices(scenario, CORPUS, count=8)
    assert len(offered) == 8

    kin = {
        s.expected.root_cause
        for s in CORPUS
        if s.category == "database" and s.expected.root_cause
    }
    # Distractors come from the same category first, so the choice cannot be
    # made by noticing which option is about databases at all.
    assert len([label for label in offered if label in kin]) == 8


def test_the_option_set_is_identical_across_runs():
    scenario = scoreable(CORPUS)[0]
    first = choices(scenario, CORPUS, count=8)
    second = choices(scenario, CORPUS, count=8)
    assert first == second, "three repetitions are incomparable if the options move"


def test_a_wrong_answer_loses():
    scenario = scoreable(CORPUS)[0]
    offered = choices(scenario, CORPUS, count=8)
    wrong = next(label for label in offered if label != scenario.expected.root_cause)
    assert grade(scenario, wrong, offered).hit is False
    assert grade(scenario, scenario.expected.root_cause, offered).hit is True


def test_nearly_right_is_not_right():
    # No fuzzy matching: a grader that accepted a prefix would be making the
    # judgement the model was asked to make.
    scenario = scoreable(CORPUS)[0]
    offered = choices(scenario, CORPUS)
    truncated = (scenario.expected.root_cause or "")[:-6]
    assert grade(scenario, truncated, offered).hit is False


def test_an_answer_outside_the_options_is_a_protocol_failure_not_a_miss():
    scenario = scoreable(CORPUS)[0]
    offered = choices(scenario, CORPUS, count=8)
    graded = grade(scenario, "something_nobody_offered", offered)
    assert graded.off_menu is True
    assert graded.hit is False

    summary = summarise([graded], CORPUS)
    # Counted apart, so a model that cannot follow the output format is not
    # reported as a model that cannot reason.
    assert summary.off_menu == 1


def test_no_answer_is_distinguished_from_a_wrong_answer():
    scenario = scoreable(CORPUS)[0]
    offered = choices(scenario, CORPUS)
    graded = grade(scenario, None, offered)
    assert graded.answer is None
    assert graded.off_menu is False
    assert summarise([graded], CORPUS).unanswered == 1


def test_chain_credit_rewards_order():
    expected = ("deploy", "query_volume", "pool_saturation", "timeout")
    assert chain_credit(expected, expected) == 1.0
    assert chain_credit((), expected) == 0.0
    in_order = chain_credit(("deploy", "pool_saturation"), expected)
    reversed_order = chain_credit(("pool_saturation", "deploy"), expected)
    assert in_order > reversed_order
    # Padding the answer with the whole world does not earn full credit.
    assert chain_credit(("x", "y", "z"), expected) == 0.0


def test_chain_credit_is_not_folded_into_accuracy():
    scenario = scoreable(CORPUS)[0]
    offered = choices(scenario, CORPUS)
    wrong = next(label for label in offered if label != scenario.expected.root_cause)
    graded = grade(scenario, wrong, offered, chain=scenario.expected.causal_chain)
    summary = summarise([graded], CORPUS)
    # A perfect chain with the wrong root cause is 0% accuracy, and the chain
    # figure survives beside it rather than propping it up.
    assert summary.top1 == 0.0
    assert summary.chain == pytest.approx(1.0)


def test_nothing_scored_is_absent_rather_than_zero():
    empty = Accuracy()
    assert empty.top1 is None
    assert empty.baseline is None
    assert empty.interval is None
    assert empty.above_chance is None


def test_the_baseline_follows_the_options_offered():
    scenario = scoreable(CORPUS)[0]
    wide = summarise([grade(scenario, None, choices(scenario, CORPUS))], CORPUS)
    narrow = summarise([grade(scenario, None, choices(scenario, CORPUS, count=8))], CORPUS)
    assert wide.baseline == pytest.approx(1 / 60)
    assert narrow.baseline == pytest.approx(1 / 8)
    # A result from the narrow condition is a weaker claim than the same
    # percentage from the wide one, and the baseline is what says so.
    assert narrow.baseline > wide.baseline


def test_a_result_that_does_not_clear_its_baseline_says_so():
    scenario = scoreable(CORPUS)[0]
    offered = choices(scenario, CORPUS, count=4)
    wrong = next(label for label in offered if label != scenario.expected.root_cause)

    # Two correct in eight, against a one-in-four baseline: 25% accuracy that
    # is exactly chance, and the interval is far too wide to claim otherwise.
    answers = [scenario.expected.root_cause] * 2 + [wrong] * 6
    summary = summarise([grade(scenario, a, offered) for a in answers], CORPUS)
    assert summary.top1 == pytest.approx(0.25)
    assert summary.above_chance is False


def test_a_strong_result_clears_its_baseline():
    scored = scoreable(CORPUS)
    graded = [grade(s, s.expected.root_cause, choices(s, CORPUS)) for s in scored]
    summary = summarise(graded, CORPUS)
    assert summary.top1 == 1.0
    assert summary.above_chance is True
    low, high = summary.interval
    assert low > 0.9 and high <= 1.0


def test_the_interval_narrows_as_the_sample_grows():
    narrow = wilson(5, 10)
    wide = wilson(50, 100)
    assert (wide[1] - wide[0]) < (narrow[1] - narrow[0])
    for hits, n in ((0, 30), (30, 30)):
        low, high = wilson(hits, n)
        assert 0.0 <= low <= high <= 1.0, "the interval must stay inside 0 to 1"


def test_categories_are_kept_apart():
    scored = scoreable(CORPUS)
    graded = [grade(s, s.expected.root_cause, choices(s, CORPUS)) for s in scored]
    summary = summarise(graded, CORPUS)
    assert set(summary.by_category) == {s.category for s in scored}
    # Security is the category inject.py cannot inject, so a reader has to be
    # able to see it separately rather than averaged in.
    assert "security" in summary.by_category


def test_the_leakage_limitation_is_stated_in_the_module():
    # It is quoted in the paper's limitations. If somebody deletes it, that
    # should break a test rather than silently improve the write-up.
    assert "reading the option text" in LEAKAGE


def test_an_unscoreable_scenario_cannot_be_offered_options():
    scenario = next(s for s in CORPUS if not s.expected.root_cause)
    with pytest.raises(ValueError, match="authors no root cause"):
        choices(scenario, CORPUS)
