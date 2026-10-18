"""Shailaputri v0 — causality, scoring through the shared harness, and learning.

The property everything rests on: a feature at time t depends only on values
up to t. If it peeked at the future, the "online" scores would be fiction.
"""

from __future__ import annotations

import numpy as np
from pashupatastra.evaluation import Series, evaluate

from sati.detect import features as feats
from sati.detect import model


def spiky(n=1500, seed=0, spikes=(700, 1100)):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    x = 50 + 10 * np.sin(2 * np.pi * t / 288) + rng.normal(0, 1, n)
    ranges = []
    for s in spikes:
        x[s : s + 20] += 25
        ranges.append((s - 5, s + 30))
    return x, ranges


def test_features_never_look_ahead():
    x, _ = spiky()
    before = feats.features(x)
    future = x.copy()
    future[1000:] += 500  # change only the future
    after = feats.features(future)
    np.testing.assert_allclose(before.iloc[:1000].to_numpy(), after.iloc[:1000].to_numpy(), equal_nan=True)


def test_features_are_scale_free():
    x, _ = spiky(seed=3)
    small, large = feats.features(x), feats.features(x * 1000)
    np.testing.assert_allclose(small.to_numpy(), large.to_numpy(), atol=1e-6, equal_nan=True)


def test_warmup_is_not_judged():
    x, ranges = spiky()
    probs = np.full(len(x), np.nan)
    score = evaluate(model.Replay(probs, 0.5), Series("s", list(x), ranges))
    assert score.warmup_samples == len(x)
    assert score.false_positives == score.true_positives == 0


def test_it_learns_spikes_on_series_it_never_saw():
    train = [spiky(seed=s) for s in range(6)]
    booster = model.train([feats.features(x) for x, _ in train], [feats.labels(len(x), r) for x, r in train])
    x, ranges = spiky(seed=99, spikes=(800, 1300))
    probs = model.probabilities(booster, feats.features(x))
    score = evaluate(model.Replay(probs, 0.5), Series("held-out", list(x), ranges))
    assert score.recall == 1.0
    assert score.false_alarms_per_1000 < 50
