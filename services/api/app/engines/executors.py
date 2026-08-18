"""Real executors — the write side.

Connectors are read-only by construction; this is the one module in the system
that changes anything. Three rules hold it in place:

**An executor never receives a command.** It receives a registered `ActionSpec`
and a parameter dict, and maps that to a specific call. There is no path from
model text to a shell string — the closed registry is what makes that true, and
an executor that accepted a command would quietly undo it.

**Every executor is reachable only through `astra.execute`**, which requires a
Dharma verdict. Nothing here is exported in a form that is convenient to call
directly, and the verdict requirement is enforced there rather than repeated
here — one gate, not several that can disagree.

**Live execution is opt-in per environment and off by default.** A misconfigured
deployment must fail closed, into dry-run, not into production writes.

Kubernetes goes through `kubectl` against the active kubeconfig, mirroring the
Phase 1 connector: on EKS the same calls work unchanged, and only authentication
differs — which is IRSA, not anything in this file (the Platform ADR).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable

from pashupatastra import ActionSpec
from pashupatastra.incidents import VerificationCheck
from pashupatastra.observation import WindowObserver, as_checks

DEFAULT_TIMEOUT = 60.0
"""Longer than the connectors' read timeout: a rollout takes time to settle, and
cutting it off early would report failure for something still in progress."""


class ExecutorError(RuntimeError):
    """A write did not complete. Raised so the remediation loop can roll back."""


def _require(params: dict[str, str], *names: str) -> list[str]:
    """Fail loudly on a missing parameter.

    A `kubectl` invocation with an empty namespace does not error — it targets
    `default`, which is a different cluster region than the caller meant. Missing
    parameters have to be caught here, not discovered by their blast radius.
    """
    missing = [name for name in names if not params.get(name)]
    if missing:
        raise ExecutorError(f"missing required parameter(s): {', '.join(missing)}")
    return [params[name] for name in names]


class KubernetesExecutor:
    """restart · scale · rollback · halt, via kubectl."""

    name = "kubernetes"

    def __init__(
        self,
        context: str | None = None,
        binary: str = "kubectl",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.context = context
        self.binary = binary
        self.timeout = timeout

    def _kubectl(self, *args: str) -> str:
        executable = shutil.which(self.binary) or self.binary
        command = [executable]
        if self.context:
            command += ["--context", self.context]
        command += list(args)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as error:
            raise ExecutorError(f"{self.binary} not found on PATH") from error
        except subprocess.TimeoutExpired as error:
            # A timeout is genuinely ambiguous — the rollout may still be in
            # progress. Raised so the loop rolls back rather than assuming
            # either outcome.
            raise ExecutorError(f"{self.binary} timed out after {self.timeout}s") from error

        if completed.returncode != 0:
            raise ExecutorError(
                f"{' '.join(args)} failed ({completed.returncode}): "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )
        return completed.stdout.strip()

    def run(self, action: ActionSpec, params: dict[str, str]) -> str:
        match action.id:
            case "restart_service":
                namespace, deployment = _require(params, "namespace", "deployment")
                return self._kubectl(
                    "rollout", "restart", f"deployment/{deployment}", "-n", namespace
                )

            case "scale_service":
                namespace, deployment, replicas = _require(
                    params, "namespace", "deployment", "replicas"
                )
                return self._kubectl(
                    "scale", f"deployment/{deployment}", f"--replicas={replicas}", "-n", namespace
                )

            case "rollback_deployment":
                namespace, deployment = _require(params, "namespace", "deployment")
                return self._kubectl(
                    "rollout", "undo", f"deployment/{deployment}", "-n", namespace
                )

            case "redeploy_version":
                namespace, deployment, image = _require(
                    params, "namespace", "deployment", "image"
                )
                container = params.get("container", deployment)
                return self._kubectl(
                    "set", "image", f"deployment/{deployment}",
                    f"{container}={image}", "-n", namespace,
                )

            case "disable_deployment":
                namespace, deployment = _require(params, "namespace", "deployment")
                return self._kubectl(
                    "rollout", "pause", f"deployment/{deployment}", "-n", namespace
                )

            case _:
                raise ExecutorError(f"{self.name} executor cannot perform {action.id!r}")

    # -- observation ----------------------------------------------------------

    def observe(self, action: ActionSpec, params: dict[str, str]) -> list[VerificationCheck]:
        """Grade the action's declared post-state against the cluster.

        Observational only — it asks the cluster what is true and compares. It
        never asks whether the action "seemed to work", and an unreadable answer
        grades as unobserved rather than as a pass.
        """
        checks: list[VerificationCheck] = []
        namespace = params.get("namespace", "default")
        deployment = params.get("deployment")

        if not deployment:
            return [VerificationCheck(name="deployment", expected="named", observed=None)]

        try:
            status = self._kubectl(
                "rollout", "status", f"deployment/{deployment}",
                "-n", namespace, "--timeout=30s",
            )
            rolled_out = "successfully rolled out" in status
            checks.append(
                VerificationCheck(
                    name="rollout",
                    expected="complete",
                    observed=status[:120],
                    passed=rolled_out,
                )
            )
        except ExecutorError as error:
            # Observed as a failure to observe, not as a failed rollout: those
            # are different, and only one of them justifies a rollback claim.
            checks.append(
                VerificationCheck(
                    name="rollout", expected="complete", observed=None, passed=None
                )
            )
            checks[-1].observed = f"unobservable: {error}"

        if "replicas" in params:
            try:
                observed = self._kubectl(
                    "get", f"deployment/{deployment}", "-n", namespace,
                    "-o", "jsonpath={.status.readyReplicas}",
                )
                checks.append(
                    VerificationCheck(
                        name="replicas",
                        expected=params["replicas"],
                        observed=observed or "0",
                        passed=(observed or "0") == params["replicas"],
                    )
                )
            except ExecutorError:
                checks.append(
                    VerificationCheck(
                        name="replicas", expected=params["replicas"], observed=None
                    )
                )

        return checks


class NotifyExecutor:
    """Ticketing and notification — the honest default when acting is unsafe.

    Deliberately trivial and risk-0. It exists because "tell a human" must be a
    first-class registered action rather than a fallback that happens in
    application code: if escalation is not an action, it is not audited, not
    measured, and not something the policy layer can choose.
    """

    name = "notify"

    def __init__(self, sink: list[str] | None = None) -> None:
        # A list rather than a real pager: routing is deployment configuration,
        # and hard-coding a provider here would put a vendor inside the engine.
        self.sink = sink if sink is not None else []

    def run(self, action: ActionSpec, params: dict[str, str]) -> str:
        match action.id:
            case "notify_engineer":
                message = params.get("message", "Pashupatastra requires attention")
                self.sink.append(message)
                return f"notified: {message}"
            case "create_ticket":
                title = params.get("title", "Incident")
                self.sink.append(f"ticket: {title}")
                return f"ticket opened: {title}"
            case _:
                raise ExecutorError(f"{self.name} executor cannot perform {action.id!r}")

    def observe(self, action: ActionSpec, params: dict[str, str]) -> list[VerificationCheck]:
        """A notification's post-state is that it was sent.

        Weak by nature, and honest about it: this cannot verify a human read it.
        Declared as one check so it grades rather than silently passing.
        """
        return [
            VerificationCheck(
                name="delivered",
                expected="sent",
                observed="sent" if self.sink else None,
                passed=bool(self.sink),
            )
        ]


def windowed_observer(router: "Router", observer: WindowObserver | None = None) -> Callable[
    [ActionSpec, dict[str, str]], list[VerificationCheck]
]:
    """Adapt the router into an observer the remediation loop can use.

    Samples over the action's window instead of once, so a metric that is merely
    bouncing does not read as recovery.
    """
    watcher = observer or WindowObserver(sleep=time.sleep)

    def observe(action: ActionSpec, params: dict[str, str]) -> list[VerificationCheck]:
        result = watcher.watch(action.id, lambda: router.observe(action, params))
        return as_checks(result)

    return observe


class Router:
    """Sends each action to the executor that owns it.

    A closed mapping rather than a lookup by convention: an action with no
    executor must fail loudly at execution time, because the alternative is an
    action that appears to run and does nothing — which verification would then
    correctly report as a failure, sending the loop into a rollback for something
    that never happened.
    """

    def __init__(self, kubernetes: KubernetesExecutor, notify: NotifyExecutor) -> None:
        self._owners = {
            "restart_service": kubernetes,
            "scale_service": kubernetes,
            "rollback_deployment": kubernetes,
            "redeploy_version": kubernetes,
            "disable_deployment": kubernetes,
            "notify_engineer": notify,
            "create_ticket": notify,
        }

    def owner(self, action_id: str) -> KubernetesExecutor | NotifyExecutor:
        try:
            return self._owners[action_id]
        except KeyError:
            raise ExecutorError(
                f"no executor owns {action_id!r} — register one, or the action is "
                "declarable but not performable"
            ) from None

    def run(self, action: ActionSpec, params: dict[str, str]) -> str:
        return self.owner(action.id).run(action, params)

    def observe(self, action: ActionSpec, params: dict[str, str]) -> list[VerificationCheck]:
        return self.owner(action.id).observe(action, params)

    def covers(self, action_id: str) -> bool:
        return action_id in self._owners
