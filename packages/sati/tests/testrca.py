"""Sati-RCA v0 — features, scoring, splits and the ranker, on synthetic incidents.

The real data is only touched by the training workflow. These tests pin the
properties that make its numbers mean something: features are relative to each
series' own baseline, a case never sits on both sides of a split, a system held
out is entirely held out, and the score counts a missing root cause as a miss.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sati.rca import features as feats
from sati.rca import model
from sati.rca.evaluate import score, wilson
from sati.rca.run import splits

INJECT = 10_000


def incident(root: str, services=("api", "db", "cache", "web"), scale=1.0, seed=0, fault="cpu"):
    """Ten minutes before and after an injection; the root shifts at INJECT,
    one other service follows 60 s later and less, the rest are noise."""
    rng = np.random.default_rng(seed)
    times = np.arange(INJECT - 600, INJECT + 600)
    data = {"time": times}
    follower = next(s for s in services if s != root)
    for service in services:
        for metric in ("cpu", "mem", "latency"):
            base = rng.normal(50 * scale, 2 * scale, times.size)
            if service == root and metric == fault:
                base[times >= INJECT] += 40 * scale
            if service == follower and metric == "latency":
                base[times >= INJECT + 60] += 10 * scale
            data[f"{service}_{metric}"] = base
    return pd.DataFrame(data)


def table_for(n_per_system=6):
    rows = []
    for system, services, scale in (
        ("a", ("api", "db", "cache", "web"), 1.0),
        ("b", ("orders", "carts", "user", "pay", "edge"), 100.0),
        ("c", ("ts-auth", "ts-order", "ts-route"), 0.01),
    ):
        for i in range(n_per_system):
            root = services[i % len(services)]
            fault = ("cpu", "mem")[i % 2]
            frame = incident(root, services, scale, seed=hash((system, i)) % 2**32, fault=fault)
            t, _ = feats.incident_features(frame, INJECT)
            t["case"] = f"{system}-{i}"
            t["system"] = system
            t["dataset"] = f"RE1-{system}"
            t["fault"] = fault
            t["repetition"] = i // len(services) + 1
            t["root"] = root
            t["label"] = (t["service"] == root).astype(int)
            rows.append(t)
    return pd.concat(rows, ignore_index=True)


def test_columns_split_on_the_last_underscore():
    assert feats.split_column("ts-auth-service_latency-90") == ("ts-auth-service", "latency-90")
    assert feats.split_column("frontend-external_load") == ("frontend-external", "load")


def test_metric_names_from_different_systems_share_families():
    assert feats.family("latency-50") == feats.family("latency") == "latency"
    assert feats.family("workload") == feats.family("load") == "traffic"


def test_the_shifted_service_has_the_largest_shift():
    table, provenance = feats.incident_features(incident("db"), INJECT)
    top = table.sort_values("shift_any", ascending=False)["service"].iloc[0]
    assert top == "db"
    assert provenance[("db", "shift_cpu")] == "db_cpu"
    assert provenance[("db", "peak_any")] == "db_cpu"


def test_features_do_not_depend_on_the_system_scale():
    """The same incident at 1x and 1000x must look the same to the model."""
    small, _ = feats.incident_features(incident("api", scale=1.0, seed=3), INJECT)
    large, _ = feats.incident_features(incident("api", scale=1000.0, seed=3), INJECT)
    cols = feats.feature_columns(small)
    pd.testing.assert_frame_equal(
        small[cols].round(6), large[cols].round(6), check_exact=False, atol=1e-4
    )


def test_a_case_with_no_baseline_is_kept_not_dropped():
    frame = incident("db")
    table, _ = feats.incident_features(frame[frame["time"] >= INJECT], INJECT)
    assert len(table) == 4
    assert table["shift_any"].isna().all()


def test_wilson_matches_a_known_value():
    low, high = wilson(8, 10)
    assert low == pytest.approx(0.4902, abs=1e-3)
    assert high == pytest.approx(0.9433, abs=1e-3)


def test_a_missing_root_counts_as_a_miss():
    result = score([1, 2, None, 6])
    assert result["ac@1"] == 0.25
    assert result["ac@3"] == 0.5
    assert result["n"] == 4


def test_no_case_is_on_both_sides_and_a_held_out_system_is_wholly_out():
    table = table_for()
    for scheme, fold, mask in splits(table):
        train, test = table[~mask], table[mask]
        assert not set(train["case"]) & set(test["case"])
        if scheme == "leave-one-system-out":
            assert set(test["system"]) == {fold}
            assert fold not in set(train["system"])


def test_the_ranker_finds_roots_on_a_system_it_never_saw():
    table = table_for()
    features = feats.feature_columns(table)
    train, test = table[table["system"] != "c"], table[table["system"] == "c"]
    booster = model.train_ranker(train, features)
    ranking = model.predict(booster, test, features)
    roots = test.groupby("case")["root"].first()
    hits = sum(model.position(ranking[c], r) == 1 for c, r in roots.items())
    assert hits / len(roots) >= 0.8


def test_an_explanation_cites_real_series():
    frame = incident("db")
    table, provenance = feats.incident_features(frame, INJECT)
    big = table_for()
    features = feats.feature_columns(big)
    booster = model.train_ranker(big, features)
    row = table[table["service"] == "db"].assign(**{c: np.nan for c in features if c not in table})
    reasons = model.explain(booster, row, features, provenance)
    assert reasons, "the root cause should have at least one positive reason"
    cited = [r["series"] for r in reasons if r["series"]]
    assert cited and all(c in frame.columns for c in cited)
