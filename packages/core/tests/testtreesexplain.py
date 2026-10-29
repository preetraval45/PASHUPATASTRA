"""Why a tree model scored a row as it did: ablation, one feature at a time."""

from __future__ import annotations

import pytest

from pashupatastra import trees

# Two stumps: E5 > 2 adds 3.0; E9 > 0 adds 0.5. Missing compares as zero ("None").
MODEL = {"objective": "binary", "features": ["E5", "E9", "E1"],
         "trees": [[0, 2.0, True, 0, -1.0, 2.0], [1, 0.0, True, 0, 0.0, 0.5]]}


def test_the_feature_that_moved_the_score_most_comes_first_with_its_signed_effect():
    effects = trees.explain(MODEL, [4.0, 1.0, 7.0])
    assert [f for f, _ in effects] == ["E5", "E9", "E1"]
    assert effects[0][1] == pytest.approx(3.0) and effects[1][1] == pytest.approx(0.5)
    assert effects[2][1] == pytest.approx(0.0)


def test_absent_features_are_not_explanations():
    assert [f for f, _ in trees.explain(MODEL, [4.0, 0.0, None])] == ["E5"]
