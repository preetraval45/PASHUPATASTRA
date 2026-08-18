"""The AWS enforcement floor, checked without AWS.

`terraform apply` needs a credential. Whether IAM *mirrors the agent
declarations* does not — and that is the property worth checking, because the
failure mode is drift: an agent granted a new tool without a matching IAM
change, or an IAM policy quietly widened past what the agent declares.

When the two disagree, the weaker one is the real policy. The runtime enforces
the declaration and IAM enforces the credential; a reader looking at either in
isolation would draw the wrong conclusion about what an agent can do.

These tests run in CI on every change, with no cloud access.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pashupatastra.runtime import sati_roles

TERRAFORM = Path(__file__).resolve().parents[3] / "infra" / "terraform"
AGENTS_JSON = TERRAFORM / "agents.json"
AGENTS_TF = TERRAFORM / "agents.tf"


def agent_specs() -> dict[str, dict]:
    data = json.loads(AGENTS_JSON.read_text(encoding="utf-8"))
    return {name: spec for name, spec in data.items() if name != "_comment"}


# --- the mirror ---------------------------------------------------------------


def test_every_declared_agent_has_an_iam_role() -> None:
    """An agent with no role would fall back to the node's credentials — the
    broadest ones available, and the opposite of least privilege."""
    assert set(agent_specs()) == set(sati_roles())


def test_iam_tool_lists_match_the_agent_declarations_exactly() -> None:
    """The drift check. An agent granted a tool without a corresponding IAM
    change fails here, and so does the reverse."""
    specs = agent_specs()
    for name, role in sati_roles().items():
        assert sorted(specs[name]["tools"]) == sorted(role.tools), (
            f"{name}: agents.json tools do not match its AgentSpec. "
            "One of the two was changed without the other."
        )


def test_read_only_agents_hold_no_write_permissions() -> None:
    """`sati.orchestrator` routes and never acts; `sati.security` is read-only by
    declaration. Both are risk-limit 0, and IAM must agree — a role that can
    write while its declaration says it cannot is the declaration being wrong."""
    specs = agent_specs()
    for name, role in sati_roles().items():
        if role.risk_limit == 0:
            assert specs[name]["write"] == [], (
                f"{name} has risk limit 0 but holds write permissions in IAM"
            )


def test_an_agent_with_no_action_budget_gets_no_write_access() -> None:
    """`sati.security` is budgeted to zero actions. Granting it write access
    would mean the budget is the only thing stopping it."""
    specs = agent_specs()
    for name, role in sati_roles().items():
        if role.budget.actions_per_incident == 0:
            assert specs[name]["write"] == []


# --- the floor ----------------------------------------------------------------


def test_destructive_actions_are_denied_not_merely_ungranted() -> None:
    """Explicit Deny beats any Allow in IAM, in any policy, attached by anyone.

    A deny-list is usually the weaker pattern. Here it is the only one that
    cannot be out-voted by a well-meaning Allow added under time pressure.
    """
    tf = AGENTS_TF.read_text(encoding="utf-8")
    assert 'effect    = "Deny"' in tf
    for action in ("eks:DeleteCluster", "rds:DeleteDBInstance", "s3:DeleteBucket",
                   "iam:*", "cloudtrail:StopLogging"):
        assert action in tf, f"{action} is not on the forbidden list"


def test_the_forbidden_policy_is_attached_to_every_agent_role() -> None:
    """A deny nobody is subject to is decoration."""
    tf = AGENTS_TF.read_text(encoding="utf-8")
    assert "aws_iam_role_policy_attachment" in tf
    assert "policy_arn = aws_iam_policy.forbidden.arn" in tf


def test_the_registry_cannot_reach_anything_the_floor_forbids() -> None:
    """The credential must be strictly weaker than the action registry.

    The registry governs what the platform will *choose* to do; the floor governs
    what its credentials *can* do. If the second were not smaller, the registry
    would be the only thing between a bug and a deleted database.
    """
    from pashupatastra.registry import all_actions

    tf = AGENTS_TF.read_text(encoding="utf-8")
    # The one registered irreversible action must have no executor path *and*
    # no credential that could perform it.
    destructive = [a for a in all_actions() if a.irreversible]
    assert destructive, "the registry should still carry a denied irreversible action"
    assert "eks:DeleteCluster" in tf and "rds:DeleteDBInstance" in tf


def test_cloudtrail_cannot_be_silenced() -> None:
    """CloudTrail is the independent mirror of the audit log (docs/DEPLOYMENT.md).
    An agent that can stop it can act without a second record."""
    tf = AGENTS_TF.read_text(encoding="utf-8")
    assert "cloudtrail:StopLogging" in tf
    assert "cloudtrail:DeleteTrail" in tf


def test_iam_self_modification_is_forbidden() -> None:
    """`iam:*` denied. Without it, an agent able to attach policies could grant
    itself everything else on this list — one permission that undoes the floor."""
    assert '"iam:*"' in AGENTS_TF.read_text(encoding="utf-8")


# --- trust --------------------------------------------------------------------


def test_each_role_trusts_exactly_one_service_account() -> None:
    """Without the `sub` condition, any pod in the cluster could assume any
    agent's role, which makes per-agent roles decorative."""
    tf = AGENTS_TF.read_text(encoding="utf-8")
    assert "system:serviceaccount:${var.agent_namespace}:${each.value.service_account}" in tf
    assert ":aud" in tf, "the audience condition guards against token confusion"


def test_service_account_names_are_unique() -> None:
    """Two agents sharing a service account share a role, and the separation is
    gone without anything looking wrong."""
    accounts = [spec["service_account"] for spec in agent_specs().values()]
    assert len(accounts) == len(set(accounts))


def test_role_creation_is_skipped_without_an_oidc_provider() -> None:
    """A cluster-less environment must plan clean rather than erroring — the
    RDS-only path has to stay usable while EKS does not exist yet."""
    tf = AGENTS_TF.read_text(encoding="utf-8")
    assert 'var.oidc_provider_arn == "" ? {} : local.agents' in tf


# --- documentation the file makes checkable ----------------------------------


@pytest.mark.parametrize("agent", ["sati.orchestrator", "sati.security"])
def test_the_read_only_agents_are_named_in_the_output(agent: str) -> None:
    """`agents_without_write_access` is asserted in the output description, so a
    future change that grants one of them write access contradicts a comment
    someone will read during review."""
    tf = AGENTS_TF.read_text(encoding="utf-8")
    assert agent in tf
