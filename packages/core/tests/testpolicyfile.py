"""Policy as data: Dharma's thresholds, approvers and escalation limits come from a versioned file."""

from __future__ import annotations

import json

import pytest

from pashupatastra import dharma
from pashupatastra.dharma import PolicyFileError, Tier, load_policy


def _write(tmp_path, **changes):
    policy = json.loads(dharma.POLICY_FILE.read_text(encoding="utf-8"))
    policy.update(changes)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    return path


def test_the_shipped_policy_matches_the_policy_model():
    loaded = load_policy()
    assert [c for c, _ in loaded["tiers"]] == [30, 60, 80, 100]
    assert loaded["approvers"][Tier.APPROVAL] == ["operator"]
    assert dharma.policy_model()["version"] == dharma.POLICY_VERSION


def test_every_verdict_records_the_policy_version_it_was_decided_under():
    from pashupatastra.registry import get

    verdict = dharma.evaluate(get("block_ip"), dharma.RiskContext(environment=dharma.Environment.DEV))
    assert verdict.constraints["policy_version"] == dharma.POLICY_VERSION


@pytest.mark.parametrize(
    "changes",
    [
        {"version": ""},
        {"tiers": [{"tier": "approval", "max_risk": 60, "approvers": []}]},
        {"tiers": [
            {"tier": "autonomous", "max_risk": 60, "approvers": []},
            {"tier": "approval", "max_risk": 30, "approvers": []},
            {"tier": "senior", "max_risk": 80, "approvers": []},
            {"tier": "denied", "max_risk": 100, "approvers": []},
        ]},
        {"tiers": [
            {"tier": "autonomous", "max_risk": 30, "approvers": []},
            {"tier": "approval", "max_risk": 60, "approvers": []},
            {"tier": "senior", "max_risk": 80, "approvers": []},
            {"tier": "denied", "max_risk": 90, "approvers": []},
        ]},
        {"escalation": {"blast_radius_entities": 0, "blast_radius_users": 1000}},
    ],
)
def test_a_malformed_policy_is_refused_not_half_applied(tmp_path, changes):
    with pytest.raises(PolicyFileError):
        load_policy(_write(tmp_path, **changes))


def test_a_changed_file_changes_the_thresholds(tmp_path):
    path = _write(tmp_path, version="test", tiers=[
        {"tier": "autonomous", "max_risk": 10, "approvers": []},
        {"tier": "approval", "max_risk": 50, "approvers": ["lead"]},
        {"tier": "senior", "max_risk": 70, "approvers": ["director"]},
        {"tier": "denied", "max_risk": 100, "approvers": []},
    ])
    loaded = load_policy(path)
    assert loaded["tiers"][0] == (10, Tier.AUTONOMOUS) and loaded["approvers"][Tier.SENIOR] == ["director"]
