"""RP-13: the incident fixtures carry exactly the owner's answer keys.

The keys live in `benchmark/answerkeys/rp13.yaml`, committed by the owner before
any run. A fixture whose label or options differ from its key would grade
against an answer nobody wrote down, so this fails the build on any difference.
Skipped until the owner's keys exist. The commit order (keys before fixtures)
is checked in the workflow that runs the diagnosis (`diagnosis-incidents.yml`),
which has the full history.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
KEYS = ROOT / "benchmark" / "answerkeys" / "rp13.yaml"
INCIDENTS = ROOT / "benchmark" / "incidents"
UNFILLED = ("TODO", "DECIDE")


def _keys() -> dict:
    if not KEYS.exists():
        pytest.skip("the owner's answer keys (RP-13) are not committed yet")
    return {k: v for k, v in yaml.safe_load(KEYS.read_text(encoding="utf-8")).items() if k.startswith("SC-")}


def test_every_fixture_with_a_key_matches_it():
    for case, key in _keys().items():
        path = INCIDENTS / f"{case}.yaml"
        if not path.exists():
            continue  # fixture not built yet
        doc = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        assert doc.get("expectation") == key["expectation"], case
        if key.get("root_cause_label") in (None, "excluded"):
            assert not doc.get("root_cause_label"), f"{case} is excluded from scoring by its key"
            continue
        assert doc.get("root_cause_label") == key["root_cause_label"], case
        assert list(doc.get("options") or []) == list(key["options"]), case


def test_no_key_for_a_built_fixture_is_left_unfilled():
    for case, key in _keys().items():
        if (INCIDENTS / f"{case}.yaml").exists():
            text = yaml.safe_dump(key)
            assert not any(u in text for u in UNFILLED), f"{case} still has a TODO or DECIDE in the answer keys"
