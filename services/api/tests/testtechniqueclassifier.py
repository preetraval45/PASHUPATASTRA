"""Brahmacharini's TF-IDF classifier, served in pure Python, scores as it was evaluated."""

from __future__ import annotations

import json
import math

import pytest

from app.engines import techniqueclassifier as tc

FIXTURE = {
    "model": "fixture", "keep": 2, "fusion_weight": 0.8,
    "terms": ["attacker", "attacker deleted", "deleted", "logs"],
    "idf": [1.0, 2.0, 1.5, 1.2],
    "classes": [
        {"id": "T1070", "bias": 0.1, "scale": 0.01, "features": [1, 3], "weights": [127, 50]},
        {"id": "T1486", "bias": -0.2, "scale": 0.02, "features": [0], "weights": [100]},
    ],
}


@pytest.fixture
def model(tmp_path):
    path = tmp_path / "technique_classifier.json"
    path.write_text(json.dumps(FIXTURE), encoding="utf-8")
    return tc.TechniqueClassifier(path)


def test_tfidf_is_sublinear_idf_weighted_and_l2_normalised(model):
    x = model.features("The attacker deleted logs, logs, logs")
    raw = {0: 1.0, 1: 2.0, 2: 1.5, 3: (1 + math.log(3)) * 1.2}  # "the" is not in the vocabulary
    norm = math.sqrt(sum(v * v for v in raw.values()))
    assert x == pytest.approx({k: v / norm for k, v in raw.items()})


def test_probabilities_are_a_softmax_over_the_kept_weights(model):
    x = model.features("attacker deleted logs")
    logits = [0.1 + 1.27 * x[1] + 0.5 * x[3], -0.2 + 2.0 * x[0]]
    exp = [math.exp(z) for z in logits]
    p = model.probabilities("attacker deleted logs")
    assert p == pytest.approx({"T1070": exp[0] / sum(exp), "T1486": exp[1] / sum(exp)})


def test_fusion_ranks_over_the_encoders_techniques_and_unrankable_ones_go_last():
    ranked = tc.fuse({"T1070": 0.9, "T1486": 0.1, "T1059": 0.5}, {"T1070": 0.2, "T1486": 0.8}, weight=1.0)
    assert [k for _, k in ranked] == ["T1070", "T1059", "T1486"]
    ranked = tc.fuse({"T1070": 0.9, "T1486": 0.1, "T1059": 0.5}, {"T1070": 0.2, "T1486": 0.8}, weight=0.0)
    assert [k for _, k in ranked] == ["T1486", "T1070", "T1059"]


@pytest.mark.skipif(not tc.available(), reason="the classifier is exported by the Brahmacharini training run")
def test_served_classifier_matches_what_numpy_computed_at_export():
    served = tc.served()
    assert served.parity, "the export writes parity samples"
    for sample in served.parity:
        p = served.probabilities(sample["text"])
        top = sorted(p.items(), key=lambda kv: -kv[1])[: len(sample["top"])]
        assert [k for k, _ in top] == [k for k, _ in sample["top"]]
        assert [v for _, v in top] == pytest.approx([v for _, v in sample["top"]], abs=1e-4)


def test_a_sigmoid_classifier_scores_each_label_on_its_own(tmp_path):
    path = tmp_path / "mitigation_classifier.json"
    path.write_text(json.dumps({**FIXTURE, "activation": "sigmoid"}), encoding="utf-8")
    m = tc.TechniqueClassifier(path)
    x = m.features("attacker deleted logs")
    p = m.probabilities("attacker deleted logs")
    assert p["T1070"] == pytest.approx(1 / (1 + math.exp(-(0.1 + 1.27 * x[1] + 0.5 * x[3]))))
    assert p["T1486"] == pytest.approx(1 / (1 + math.exp(-(-0.2 + 2.0 * x[0]))))


@pytest.mark.skipif(not tc.mitigations_available(), reason="exported by the Skandamata training run")
def test_served_mitigation_classifier_matches_what_numpy_computed_at_export():
    served = tc.mitigations()
    for sample in served.parity:
        p = served.probabilities(sample["text"])
        top = sorted(p.items(), key=lambda kv: -kv[1])[: len(sample["top"])]
        assert [k for k, _ in top] == [k for k, _ in sample["top"]]
        assert [v for _, v in top] == pytest.approx([v for _, v in sample["top"]], abs=1e-4)


def test_a_mitigation_classifier_its_run_did_not_measure_better_is_not_served(tmp_path, monkeypatch):
    monkeypatch.setattr(tc, "FOLDER", tmp_path)
    tc._serve_flag.cache_clear()
    (tmp_path / "mitigation_classifier.json").write_text(json.dumps({**FIXTURE, "serve": False}), encoding="utf-8")
    assert tc.mitigations_available() is False
    tc._serve_flag.cache_clear()
    (tmp_path / "mitigation_classifier.json").write_text(json.dumps({**FIXTURE, "serve": True}), encoding="utf-8")
    assert tc.mitigations_available() is True
    tc._serve_flag.cache_clear()
