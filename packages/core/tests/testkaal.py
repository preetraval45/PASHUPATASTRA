"""Kaal's incident generator (RP-17): determinism, label consistency, negatives, propagation."""

from __future__ import annotations

import json

from pashupatastra.kaal.generator import FAULTS, callers_by_distance, incident
from pashupatastra.pib import SEED_CATEGORIES
from pashupatastra.registry import get as get_action

SAMPLE = [incident(7, i) for i in range(300)]


def test_the_same_seed_gives_byte_identical_incidents():
    a = json.dumps(incident(3, 42).to_json(), sort_keys=True)
    b = json.dumps(incident(3, 42).to_json(), sort_keys=True)
    assert a == b
    assert a != json.dumps(incident(4, 42).to_json(), sort_keys=True)


def test_labels_use_pib_categories_and_registered_actions():
    for inc in SAMPLE:
        label = inc.label
        if label["category"] is not None:
            assert label["category"] in SEED_CATEGORIES
        if label["action"] is not None:
            get_action(str(label["action"]))  # raises KeyError if unregistered
        assert label["outcome"] in ("remediate", "escalate", "nothing")


def test_negatives_carry_no_fault_and_no_strong_fault_signature():
    negatives = [inc for inc in SAMPLE if inc.label["outcome"] == "nothing"]
    assert negatives, "the sample should include negatives"
    for inc in negatives:
        assert inc.label["root_service"] is None and inc.label["affected"] == []
        decoys = {d["service"] for d in inc.label["decoys"]}
        for e in inc.events:
            sigma = getattr(e.payload, "deviation_sigma", None)
            if sigma is not None and abs(sigma) >= 3:
                assert e.entity_ref.id in decoys  # only a decoy may look alarming


def test_escalation_faults_have_no_action_and_remediations_have_one():
    for inc in SAMPLE:
        if inc.label["outcome"] == "escalate":
            assert inc.label["action"] is None
        if inc.label["outcome"] == "remediate":
            assert inc.label["action"] is not None


def test_every_affected_service_is_the_root_or_one_of_its_callers():
    for inc in SAMPLE:
        root = inc.label["root_service"]
        if root is None:
            continue
        upstream = {name for name, _ in callers_by_distance(str(root), inc.calls)}
        assert inc.label["affected"][0] == root
        assert set(inc.label["affected"][1:]) <= upstream


def test_decoys_are_never_the_root():
    for inc in SAMPLE:
        assert all(d["service"] != inc.label["root_service"] for d in inc.label["decoys"])


def test_the_call_graph_points_down_and_has_no_cycles():
    order = {"edge": 0, "api": 1, "backend": 2, "store": 3}
    for inc in SAMPLE[:50]:
        layer = {s.name: s.layer for s in inc.services}
        assert all(order[layer[a]] < order[layer[b]] for a, b in inc.calls)


def test_callers_by_distance_walks_up_the_graph():
    calls = [("edge", "api"), ("api", "db"), ("other", "db")]
    assert callers_by_distance("db", calls) == [("api", 1), ("other", 1), ("edge", 2)]


def test_the_catalogue_covers_all_eight_pib_categories():
    assert {f.category for f in FAULTS} == set(SEED_CATEGORIES)
