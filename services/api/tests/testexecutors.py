"""Executors — the write side.

Nothing here touches a real cluster; `kubectl` is faked at the subprocess seam.
That is a real limitation and is stated in the roadmap: these tests prove the
command construction and the failure handling, not that the cluster obeys. Live
verification against a kind cluster is a separate, still-owed step.

The weight is on the failure paths, because a write that half-succeeds is the
expensive kind.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest
from pashupatastra.registry import all_actions, get

from app.engines.executors import (
    ExecutorError,
    KubernetesExecutor,
    NotifyExecutor,
    Router,
)


class FakeKubectl:
    """Records invocations and replays scripted results."""

    def __init__(self, results: list[Any] | None = None) -> None:
        self.results = results or []
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> Any:
        self.calls.append(command)
        result = self.results.pop(0) if self.results else subprocess.CompletedProcess(
            command, 0, "ok", ""
        )
        if isinstance(result, Exception):
            raise result
        return result

    @property
    def args(self) -> list[str]:
        """The last invocation, with the binary path stripped."""
        return self.calls[-1][1:]


@pytest.fixture
def kubectl(monkeypatch: pytest.MonkeyPatch) -> FakeKubectl:
    fake = FakeKubectl()
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("shutil.which", lambda _binary: "/usr/bin/kubectl")
    return fake


# --- command construction -----------------------------------------------------


def test_restart_targets_the_named_deployment(kubectl: FakeKubectl) -> None:
    KubernetesExecutor().run(get("restart_service"), {"namespace": "prod", "deployment": "api"})
    assert kubectl.args == ["rollout", "restart", "deployment/api", "-n", "prod"]


def test_scale_passes_the_replica_count(kubectl: FakeKubectl) -> None:
    KubernetesExecutor().run(
        get("scale_service"), {"namespace": "prod", "deployment": "api", "replicas": "5"}
    )
    assert kubectl.args == ["scale", "deployment/api", "--replicas=5", "-n", "prod"]


def test_rollback_uses_rollout_undo(kubectl: FakeKubectl) -> None:
    KubernetesExecutor().run(
        get("rollback_deployment"), {"namespace": "prod", "deployment": "api"}
    )
    assert kubectl.args == ["rollout", "undo", "deployment/api", "-n", "prod"]


def test_halting_a_deployment_pauses_the_rollout(kubectl: FakeKubectl) -> None:
    KubernetesExecutor().run(
        get("disable_deployment"), {"namespace": "prod", "deployment": "api"}
    )
    assert kubectl.args == ["rollout", "pause", "deployment/api", "-n", "prod"]


def test_the_context_is_passed_when_configured(kubectl: FakeKubectl) -> None:
    """A cluster targeted by accident is the worst possible blast radius."""
    KubernetesExecutor(context="staging").run(
        get("restart_service"), {"namespace": "prod", "deployment": "api"}
    )
    assert kubectl.args[:2] == ["--context", "staging"]


# --- missing parameters fail loudly ------------------------------------------


def test_a_missing_namespace_is_refused_rather_than_defaulted(kubectl: FakeKubectl) -> None:
    """`kubectl` with no namespace does not error — it targets `default`, which
    is a different part of the cluster than the caller meant."""
    with pytest.raises(ExecutorError, match="namespace"):
        KubernetesExecutor().run(get("restart_service"), {"deployment": "api"})
    assert kubectl.calls == [], "nothing was sent to the cluster"


def test_an_empty_parameter_counts_as_missing(kubectl: FakeKubectl) -> None:
    with pytest.raises(ExecutorError, match="deployment"):
        KubernetesExecutor().run(
            get("restart_service"), {"namespace": "prod", "deployment": ""}
        )


def test_an_unsupported_action_is_refused(kubectl: FakeKubectl) -> None:
    with pytest.raises(ExecutorError, match="cannot perform"):
        KubernetesExecutor().run(get("clear_cache"), {"namespace": "p", "deployment": "d"})


# --- failure handling ---------------------------------------------------------


def test_a_nonzero_exit_raises_so_the_loop_can_roll_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeKubectl([subprocess.CompletedProcess([], 1, "", 'Error: deployments "api" not found')])
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/kubectl")

    with pytest.raises(ExecutorError, match="not found"):
        KubernetesExecutor().run(get("restart_service"), {"namespace": "p", "deployment": "api"})


def test_a_timeout_raises_rather_than_assuming_either_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timed-out rollout is genuinely ambiguous — it may still be in progress.
    Raising sends it to the rollback path instead of guessing."""
    fake = FakeKubectl([subprocess.TimeoutExpired(cmd="kubectl", timeout=60)])
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/kubectl")

    with pytest.raises(ExecutorError, match="timed out"):
        KubernetesExecutor().run(get("restart_service"), {"namespace": "p", "deployment": "api"})


def test_a_missing_binary_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeKubectl([FileNotFoundError("kubectl")])
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("shutil.which", lambda _b: None)

    with pytest.raises(ExecutorError, match="not found on PATH"):
        KubernetesExecutor().run(get("restart_service"), {"namespace": "p", "deployment": "api"})


# --- observation --------------------------------------------------------------


def test_a_completed_rollout_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeKubectl(
        [subprocess.CompletedProcess([], 0, 'deployment "api" successfully rolled out', "")]
    )
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/kubectl")

    checks = KubernetesExecutor().observe(
        get("restart_service"), {"namespace": "p", "deployment": "api"}
    )
    assert checks[0].passed is True


def test_an_unreadable_cluster_grades_as_unobserved_not_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"We could not tell" and "it did not work" are different, and only one of
    them justifies claiming the action failed."""
    fake = FakeKubectl([subprocess.CompletedProcess([], 1, "", "connection refused")])
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("shutil.which", lambda _b: "/usr/bin/kubectl")

    checks = KubernetesExecutor().observe(
        get("restart_service"), {"namespace": "p", "deployment": "api"}
    )
    assert checks[0].passed is None, "unobserved, not failed"
    assert "unobservable" in (checks[0].observed or "")


def test_an_unnamed_deployment_cannot_be_observed(kubectl: FakeKubectl) -> None:
    checks = KubernetesExecutor().observe(get("restart_service"), {})
    assert checks[0].passed is None


# --- notification -------------------------------------------------------------


def test_escalation_is_a_registered_action_not_application_code() -> None:
    """If telling a human is not an action, it is not audited, not measured, and
    not something the policy layer can choose."""
    sink: list[str] = []
    NotifyExecutor(sink).run(get("notify_engineer"), {"message": "pool exhausted"})
    assert sink == ["pool exhausted"]


def test_a_notification_is_honest_about_what_it_can_verify() -> None:
    """It cannot confirm a human read it, and says so by grading delivery only."""
    notify = NotifyExecutor([])
    unsent = notify.observe(get("notify_engineer"), {})
    assert unsent[0].passed is False

    notify.run(get("notify_engineer"), {"message": "x"})
    assert notify.observe(get("notify_engineer"), {})[0].passed is True


# --- routing ------------------------------------------------------------------


def a_router() -> Router:
    return Router(KubernetesExecutor(), NotifyExecutor([]))


def test_an_unowned_action_fails_loudly_rather_than_silently_doing_nothing() -> None:
    """An action that appears to run and does nothing would be reported by
    verification as a failure, sending the loop into a rollback for something
    that never happened."""
    with pytest.raises(ExecutorError, match="no executor owns"):
        a_router().owner("modify_db_config")


def test_the_router_covers_every_action_it_claims() -> None:
    router = a_router()
    for action_id in ("restart_service", "scale_service", "rollback_deployment",
                      "redeploy_version", "disable_deployment", "notify_engineer",
                      "create_ticket"):
        assert router.covers(action_id)


def test_which_registered_actions_have_no_executor_yet() -> None:
    """Documents the gap rather than hiding it.

    Cache and database actions are registered — the policy layer can reason about
    them and deny them — but nothing can perform them yet. That is a deliberate,
    visible state: an action that is declarable but not performable fails loudly
    at execution rather than appearing to succeed.
    """
    router = a_router()
    unperformable = {
        action.id
        for action in all_actions()
        if not router.covers(action.id) and action.base_risk > 0
    }
    assert unperformable == {"clear_cache", "warm_cache", "modify_db_config",
                             "delete_infrastructure"}


def test_every_executable_action_can_also_execute_its_rollback() -> None:
    """The runtime half of the registry guard, at the executor layer.

    A rollback that no executor owns is a rollback you cannot perform, and the
    registry check would not notice — it only looks at whether an ID was written
    down.
    """
    router = a_router()
    for action in all_actions():
        if not router.covers(action.id) or action.rollback_action_id is None:
            continue
        assert router.covers(action.rollback_action_id), (
            f"{action.id} declares rollback {action.rollback_action_id}, "
            "which no executor can perform"
        )

# --- the live-execution gates -------------------------------------------------


def test_live_execution_needs_both_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    """One flag is one accident away from a production write — someone flips
    `dry_run` for a local test, forgets, and deploys."""
    from pashupatastra.dharma import Environment

    from app.config import Settings

    assert not Settings(dry_run=True, environment=Environment.PROD,
                        live_environments=[Environment.PROD]).live_execution_enabled
    assert not Settings(dry_run=False, environment=Environment.PROD,
                        live_environments=[]).live_execution_enabled
    assert Settings(dry_run=False, environment=Environment.PROD,
                    live_environments=[Environment.PROD]).live_execution_enabled


def test_a_misconfiguration_fails_closed_into_dry_run() -> None:
    """The default must never be a write."""
    from app.config import Settings

    assert not Settings().live_execution_enabled


def test_naming_a_different_environment_does_not_grant_live_execution() -> None:
    """Promotion is explicit: proof in staging grants no production authority."""
    from pashupatastra.dharma import Environment

    from app.config import Settings

    settings = Settings(
        dry_run=False, environment=Environment.PROD, live_environments=[Environment.STAGING]
    )
    assert not settings.live_execution_enabled
