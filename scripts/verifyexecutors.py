"""Verify the executors against a real Kubernetes cluster.

The unit tests fake `kubectl` at the subprocess seam, which proves command
construction and failure handling but not that a cluster obeys. This runs the
actual `KubernetesExecutor` and the actual `Remediator` against a live cluster
and checks the observed state afterwards — the difference between "the code is
written" and evidence.

Kept as a script rather than a test because it needs a cluster: CI has none, and
a test that silently skips is worse than one that is absent, since a skip reads
as a pass in a summary line.

Setup:
    kind create cluster --name pashupatastra
    kubectl create namespace pashu-test
    kubectl create deployment checkout-api --image=registry.k8s.io/pause:3.9 \
        --replicas=2 -n pashu-test
    kubectl set image deployment/checkout-api pause=registry.k8s.io/pause:3.10 \
        -n pashu-test          # a second revision, so `rollout undo` has a target

Usage:
    python scripts/verifyexecutors.py [--context kind-pashupatastra]

Teardown:
    kind delete cluster --name pashupatastra
"""

from __future__ import annotations

import argparse
import subprocess
import sys

sys.path.insert(0, "packages/core")
sys.path.insert(0, "services/api")

from pashupatastra.dharma import (  # noqa: E402
    ActionSpec,
    Environment,
    RiskContext,
    Tier,
    Verdict,
)
from pashupatastra.incidents import VerificationCheck  # noqa: E402
from pashupatastra.registry import get  # noqa: E402
from pashupatastra.remediation import Disposition, Remediator  # noqa: E402
from pashupatastra.runtime import AgentRuntime, ToolDenied, sati_roles  # noqa: E402

from app.engines.executors import ExecutorError, KubernetesExecutor  # noqa: E402

NAMESPACE = "pashu-test"
DEPLOYMENT = "checkout-api"


def a_verdict(action_id: str) -> Verdict:
    return Verdict(
        action_id=action_id,
        incident_ref="LIVE-VERIFY",
        base_risk=10,
        adjustments=[],
        effective_risk=10,
        tier=Tier.AUTONOMOUS,
        required_approvers=[],
    )


def observed_replicas(context: str | None) -> str:
    command = ["kubectl"]
    if context:
        command += ["--context", context]
    command += [
        "get", f"deployment/{DEPLOYMENT}", "-n", NAMESPACE,
        "-o", "jsonpath={.spec.replicas}",
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()


def observed_revision(context: str | None) -> str:
    command = ["kubectl"]
    if context:
        command += ["--context", context]
    command += [
        "get", f"deployment/{DEPLOYMENT}", "-n", NAMESPACE,
        "-o", "jsonpath={.metadata.annotations.deployment\\.kubernetes\\.io/revision}",
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()


def observed_image(context: str | None) -> str:
    command = ["kubectl"]
    if context:
        command += ["--context", context]
    command += [
        "get", f"deployment/{DEPLOYMENT}", "-n", NAMESPACE,
        "-o", "jsonpath={.spec.template.spec.containers[0].image}",
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", default=None)
    args = parser.parse_args()

    executor = KubernetesExecutor(context=args.context)
    params = {"namespace": NAMESPACE, "deployment": DEPLOYMENT}
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        print(f"  {'PASS' if condition else 'FAIL'}  {label}{f' — {detail}' if detail else ''}")
        if not condition:
            failures.append(label)

    print("1. restart_service — a real rollout restart")
    executor.run(get("restart_service"), params)
    checks = executor.observe(get("restart_service"), params)
    check("rollout completed and was observed", all(c.passed for c in checks),
          "; ".join(f"{c.name}={c.passed}" for c in checks))

    print("\n2. scale_service — replicas actually change in the cluster")
    executor.run(get("scale_service"), {**params, "replicas": "3"})
    scaled = observed_replicas(args.context)
    check("cluster reports 3 replicas", scaled == "3", f"observed {scaled!r}")
    scale_checks = executor.observe(get("scale_service"), {**params, "replicas": "3"})
    check("observer graded the replica count", any(c.name == "replicas" for c in scale_checks))

    executor.run(get("scale_service"), {**params, "replicas": "2"})
    check("scaled back to 2", observed_replicas(args.context) == "2")

    print("\n3. rollback_deployment — rollout undo against real revision history")
    # Asserted on the revision, not the image: a restart creates a new revision
    # carrying the *same* image, so `rollout undo` legitimately moves between
    # revisions without changing it. The first version of this check compared
    # images and reported a false failure.
    before_revision = observed_revision(args.context)
    executor.run(get("rollback_deployment"), params)
    executor.observe(get("rollback_deployment"), params)
    after_revision = observed_revision(args.context)
    check("revision advanced, so the undo took effect",
          before_revision != after_revision, f"rev {before_revision} -> {after_revision}")

    print("\n4. failure handling — a deployment that does not exist")
    try:
        executor.run(get("restart_service"), {"namespace": NAMESPACE, "deployment": "ghost"})
        check("a missing deployment raises", False, "no error raised")
    except ExecutorError as error:
        check("a missing deployment raises ExecutorError", "not found" in str(error).lower())

    print("\n5. the full remediation loop — forced verification failure, real rollback")
    # `scale_service` rather than `restart_service`: scaling has a genuine
    # inverse (scale back to the prior count), while a restart's declared
    # "rollback" is itself and undoes nothing. Live testing is what surfaced that
    # difference — the mocked tests could not, because a fake executor cannot
    # tell a real undo from a repeat.
    calls: list[str] = []

    def runner(action: ActionSpec, p: dict[str, str]) -> str:
        calls.append(f"{action.id}(replicas={p.get('replicas')})")
        return executor.run(action, p)

    def failing_then_passing(action: ActionSpec, p: dict[str, str]) -> list[VerificationCheck]:
        if len(calls) == 1:
            return [VerificationCheck(name="health", expected="healthy",
                                      observed="crashloop", passed=False)]
        return executor.observe(action, p)

    def capture(action: ActionSpec, p: dict[str, str]) -> dict[str, str]:
        """The prior replica count — what a rollback must restore."""
        return {**p, "replicas": observed_replicas(args.context)}

    remediator = Remediator(
        runner,
        failing_then_passing,
        rollback_of=lambda i: get(get(i).rollback_action_id or i),
        capture=capture,
    )
    result = remediator.remediate(
        get("scale_service"), a_verdict("scale_service"), {**params, "replicas": "4"}
    )
    check("verification failure triggered a real rollback",
          result.disposition is Disposition.ROLLED_BACK,
          f"{result.disposition.value}: {result.reason}")
    check("the rollback restored the prior replica count, not the new one",
          observed_replicas(args.context) == "2", f"observed {observed_replicas(args.context)!r}")
    check("both the action and its rollback ran against the cluster", len(calls) == 2, str(calls))

    print("\n6. a self-rollback that cannot undo escalates instead of repeating")
    # `restart_service` declares itself as its rollback. Repeating it undoes
    # nothing, and Kubernetes rejects two restarts within a second — which the
    # first version of this script surfaced as a spurious ROLLBACK_FAILED page.
    restart_calls: list[str] = []

    def restart_runner(action: ActionSpec, p: dict[str, str]) -> str:
        restart_calls.append(action.id)
        return executor.run(action, p)

    escalating = Remediator(
        restart_runner,
        lambda a, p: [VerificationCheck(name="health", expected="healthy",
                                        observed="crashloop", passed=False)],
        rollback_of=lambda i: get(get(i).rollback_action_id or i),
    )
    escalated = escalating.remediate(
        get("restart_service"), a_verdict("restart_service"), params
    )
    check("escalated rather than restarting twice",
          escalated.disposition is Disposition.ESCALATED, escalated.disposition.value)
    check("the pointless second restart was never sent", len(restart_calls) == 1,
          str(restart_calls))

    print("\n7. the agent runtime — sati.infrastructure acting on the real cluster")
    # The fleet wired end to end: declaration → allow-list → Dharma verdict →
    # executor → cluster. Declared limits are only limits if something enforces
    # them against a system that can actually be changed.
    roles = sati_roles()
    infra = AgentRuntime(
        spec=roles["sati.infrastructure"],
        tools={
            "astra.scale_service": lambda **kw: executor.run(get("scale_service"), kw),
            "astra.rollback_deployment": lambda **kw: executor.run(
                get("rollback_deployment"), kw
            ),
            # Offered but undeclared for this role — the runtime must not hold it.
            "astra.modify_db_config": lambda **kw: "should be unreachable",
        },
        environment=Environment.DEV,
        incident_id="LIVE-VERIFY",
    )

    check("the undeclared tool was never even held",
          "astra.modify_db_config" not in infra.available_tools(),
          str(infra.available_tools()))

    infra.call("astra.scale_service", namespace=NAMESPACE, deployment=DEPLOYMENT, replicas="3")
    infra.record_action()
    check("the agent scaled the real deployment", observed_replicas(args.context) == "3",
          f"observed {observed_replicas(args.context)!r}")

    try:
        infra.call("astra.modify_db_config", namespace=NAMESPACE)
        check("an undeclared tool is refused", False, "it was allowed")
    except ToolDenied:
        check("an undeclared tool is refused", True)

    ceiling = infra.authorize("modify_db_config", RiskContext(environment=Environment.DEV))
    check("an action above the agent's ceiling is denied by Dharma",
          ceiling.tier is Tier.DENIED, f"tier={ceiling.tier.value}, risk 65 vs ceiling 45")

    # Put the cluster back where the run found it.
    infra.call("astra.scale_service", namespace=NAMESPACE, deployment=DEPLOYMENT, replicas="2")
    check("restored to 2 replicas", observed_replicas(args.context) == "2")

    print("\n" + ("FAILURES: " + ", ".join(failures) if failures else "All live checks passed."))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
