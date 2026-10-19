"""RP-10 — McNemar and the paired bootstrap give the answers the textbook does."""

from __future__ import annotations

import pytest

from pashupatastra.significance import bootstrap_difference, mcnemar


def test_no_disagreement_is_no_evidence():
    assert mcnemar([(True, True), (False, False)]).p_value == 1.0


def test_a_lopsided_disagreement_is_significant():
    result = mcnemar([(True, False)] * 10)
    assert result.only_a == 10 and result.only_b == 0
    assert result.p_value == pytest.approx(2 / 2**10)


def test_a_balanced_disagreement_is_not():
    result = mcnemar([(True, False)] * 5 + [(False, True)] * 5)
    assert result.p_value == 1.0


def test_concordant_pairs_do_not_move_the_test():
    base = [(True, False)] * 6 + [(False, True)] * 1
    padded = base + [(True, True)] * 100 + [(False, False)] * 100
    assert mcnemar(base).p_value == mcnemar(padded).p_value


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def test_identical_arms_give_an_interval_around_zero():
    data = {f"s{i}": [i % 3, i % 2] for i in range(30)}
    lo, hi = bootstrap_difference(data, data, mean)
    assert lo == hi == 0.0


def test_a_consistent_gap_excludes_zero():
    a = {f"s{i}": [1.0, 1.0] for i in range(30)}
    b = {f"s{i}": [0.0, 0.2] for i in range(30)}
    lo, hi = bootstrap_difference(a, b, mean)
    assert lo > 0 and hi <= 1.0


def test_scenarios_only_one_arm_ran_are_ignored():
    assert bootstrap_difference({"x": [1]}, {"y": [0]}, mean) is None
