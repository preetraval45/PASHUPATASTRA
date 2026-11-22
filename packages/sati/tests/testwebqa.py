"""Brahmacharini's passage ranker: labels, the metric's denominator, and the model it serves."""

from __future__ import annotations

import pytest

from pashupatastra import trees, webread
from sati.webqa import run

DOCS = [
    webread.Document("Paris", "https://en.wikipedia.org/wiki/Paris",
                     "Paris is the capital and largest city of France. It lies on the Seine.", "Wikipedia", rank=1),
    webread.Document("Capital punishment in France", "https://en.wikipedia.org/wiki/C",
                     "Capital punishment in France is banned by the Constitution.", "Wikipedia", rank=0),
]


def test_an_answer_matches_whole_words_after_normalising() -> None:
    assert run.contains("The capital is Paris.", ["paris"])
    assert run.contains("It was won by the Beatles in 1964.", ["Beatles"])
    assert not run.contains("Parisian cafes", ["Paris"])


def test_a_question_with_no_candidates_counts_as_a_miss() -> None:
    rows = [{"candidates": [{"f": {"x": 1.0}, "y": 1}]}, {"candidates": []}]
    assert run.answer_at_1(rows, lambda f: f["x"]) == [1, 0]


def test_questions_with_nothing_to_order_are_not_trained_on() -> None:
    rows = [{"candidates": [{"f": dict.fromkeys(webread.FEATURES, 0.0), "y": 1}] * 2},
            {"candidates": [{"f": dict.fromkeys(webread.FEATURES, 0.0), "y": 0}] * 2}]
    X, _, groups = run.matrix(rows)
    assert len(X) == 0 and groups == []


def test_the_sign_test_counts_only_disagreements() -> None:
    assert run.sign_test([1, 1, 0, 1], [1, 0, 0, 1]) == {"wins": 1, "losses": 0, "p": 1.0}


def test_every_candidate_carries_every_feature() -> None:
    found = webread.candidates("What is the capital of France?", DOCS)
    assert found and all(set(f) == set(webread.FEATURES) for _, _, f in found)


def test_the_trained_ranker_is_served_exactly() -> None:
    lgb = pytest.importorskip("lightgbm")
    import numpy as np

    rng = np.random.default_rng(0)
    X = rng.random((200, len(webread.FEATURES)))
    y = (X[:, 0] > 0.5).astype(int)
    booster = lgb.train({**run.PARAMS, "verbose": -1}, lgb.Dataset(X, y, group=[10] * 20), 20)
    model = trees.compact(booster.dump_model(), list(webread.FEATURES))
    score = webread.scorer(model)
    for row in X[:20]:
        served = score(dict(zip(webread.FEATURES, row, strict=True)))
        assert served == pytest.approx(booster.predict(row.reshape(1, -1), raw_score=True)[0], abs=1e-9)
