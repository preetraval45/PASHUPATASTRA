"""Skandamata v0 — the ground truth, the set-aware measures and the baselines."""

from __future__ import annotations

import numpy as np
import pytest

from sati.respond import metrics
from sati.respond.data import mitigations


def _bundle() -> dict:
    def coa(i: str, name: str) -> dict:
        return {"type": "course-of-action", "id": f"course-of-action--{i}", "name": name, "description": f"{name} text",
                "external_references": [{"source_name": "mitre-attack", "external_id": f"M10{i}"}]}

    def rel(kind: str, src: str, dst: str) -> dict:
        return {"type": "relationship", "relationship_type": kind, "source_ref": src, "target_ref": dst}

    return {"objects": [
        coa("01", "Audit"), coa("02", "User Training"),
        {**coa("03", "Old"), "x_mitre_deprecated": True},
        rel("mitigates", "course-of-action--01", "attack-pattern--parent"),
        rel("mitigates", "course-of-action--02", "attack-pattern--parent"),
        rel("mitigates", "course-of-action--03", "attack-pattern--other"),
        rel("subtechnique-of", "attack-pattern--child", "attack-pattern--parent"),
    ]}


def test_deprecated_mitigations_are_dropped_and_subtechniques_inherit():
    items, by_technique = mitigations(_bundle())
    assert [m.attack_id for m in items] == ["M1001", "M1002"]
    assert by_technique["attack-pattern--child"] == by_technique["attack-pattern--parent"]
    assert "attack-pattern--other" not in by_technique  # its only mitigation is deprecated


def test_score_one_is_set_aware():
    s = metrics.score_one([3, 1, 0, 2, 4, 5], frozenset({1, 2}))
    assert s["hit@1"] == 0.0 and s["mrr"] == 0.5
    assert s["recall@5"] == 1.0 and s["precision@5"] == 0.4
    perfect = metrics.score_one([1, 2, 0], frozenset({1, 2}))
    assert perfect["ndcg@10"] == pytest.approx(1.0)


def test_popularity_ranks_by_training_frequency_for_everyone():
    scores = metrics.popularity([frozenset({2}), frozenset({2, 0})], size=3, rows=2)
    assert (np.argsort(-scores[0])[:2] == [2, 0]).all() and (scores[0] == scores[1]).all()


def test_two_hop_carries_technique_scores_to_their_mitigations():
    technique_scores = np.array([[0.1, 0.9]])
    out = metrics.two_hop(technique_scores, [frozenset({0}), frozenset({2})], size=3, k=1)
    assert np.argmax(out[0]) == 2 and out[0, 0] == 0


def test_the_recommender_learns_a_separable_toy_task():
    torch = pytest.importorskip("torch")
    from sati.respond.run import Recommender, predict, targets

    torch.manual_seed(0)
    texts = ["encrypts files ransom note"] * 20 + ["phishing email link credential"] * 20
    golds = [frozenset({0})] * 20 + [frozenset({1, 2})] * 20
    model = Recommender(labels=3, width=16, hidden=16, buckets=1024, dropout=0.0)
    opt = torch.optim.Adam(model.parameters(), lr=0.05)
    for _ in range(60):
        loss = torch.nn.functional.binary_cross_entropy_with_logits(model(texts), targets(golds, 3))
        opt.zero_grad()
        loss.backward()
        opt.step()
    p = predict(model, ["encrypts files ransom note", "phishing email link credential"])
    assert p[0].argmax() == 0 and set(np.argsort(-p[1])[:2]) == {1, 2}
