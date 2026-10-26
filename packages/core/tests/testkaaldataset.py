"""Kaal dataset v1 (RP-18): split rules, the contamination guard and the manifest."""

from __future__ import annotations

from pashupatastra.kaal.dataset import HELD_OUT_FAULTS, SPLITS, build, shape, signature, split_of
from pashupatastra.kaal.generator import incident

MANIFEST = build(1500, seed=11)


def test_held_out_faults_only_appear_in_their_test_split():
    for i in range(400):
        inc = incident(11, i)
        if inc.label["fault_type"] in HELD_OUT_FAULTS:
            assert split_of(inc) == "test-ood-fault"
        else:
            assert split_of(inc) != "test-ood-fault"


def test_a_topology_shape_never_spans_ood_and_training():
    by_shape: dict[str, set[str]] = {}
    for i in range(600):
        inc = incident(11, i)
        if inc.label["fault_type"] in HELD_OUT_FAULTS:
            continue
        by_shape.setdefault(shape(inc), set()).add(split_of(inc))
    for splits in by_shape.values():
        assert not ("test-ood-topology" in splits and len(splits) > 1)


def test_the_guard_passes_and_no_training_signature_reaches_a_test_split():
    guard = MANIFEST["guard"]
    assert guard["passed"] is True
    assert guard["pib_reference_topology_matches"] == 0
    assert all(v == 0 for v in guard["train_signatures_also_in"].values())
    assert guard["pending"], "unchecked sources must be named, not omitted"


def test_the_manifest_accounts_for_every_incident():
    m = MANIFEST
    kept = sum(m["splits"][s]["incidents"] for s in SPLITS)
    removed = sum(m["guard"]["removed_from_tests_as_repeats_of_training"].values())
    assert kept + removed == m["n"] == 1500
    assert all(len(m["splits"][s]["ids_sha256"]) == 64 for s in SPLITS)


def test_the_manifest_is_reproducible():
    assert build(300, seed=11) == build(300, seed=11)


def test_signatures_ignore_names_but_not_structure():
    a, b = incident(11, 1), incident(11, 2)
    assert signature(a) == signature(a)
    assert signature(a) != signature(b)


def test_assign_agrees_with_the_manifest_counts():
    from pashupatastra.kaal.dataset import assign

    splits = assign(1500, seed=11)
    for s in SPLITS:
        assert sum(1 for v in splits.values() if v == s) == MANIFEST["splits"][s]["incidents"]
    removed = sum(MANIFEST["guard"]["removed_from_tests_as_repeats_of_training"].values())
    assert sum(1 for v in splits.values() if v is None) == removed
