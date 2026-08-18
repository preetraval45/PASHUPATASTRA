"""Fault injection, and an honest account of what cannot be injected.

The capability map below is the important part. Half the corpus describes faults
that a five-deployment reference stack genuinely cannot reproduce — a
supply-chain compromise, a half-applied migration, an exfiltration. Those are
excluded by name with a stated reason, because the alternative is a harness that
runs what is easy and reports it as the corpus, and the easy scenarios are
biased in exactly the direction that flatters the system.
"""

from __future__ import annotations

from dataclasses import dataclass

from pashupatastra.pib import Outcome, PibScenario

from .stack import OBSERVABLE, SERVICES, EphemeralStack, kubectl

BROKEN_IMAGE = "registry.k8s.io/pause:pib-does-not-exist"

# Fault types with no injector, and why. Each reason states a real obstacle
# rather than "not implemented", so a reader can tell which of these are
# waiting on work and which are waiting on a decision.
UNSUPPORTED: dict[str, str] = {
    "security": (
        "requires simulating an adversary; an infrastructure fault cannot stand in "
        "for an intrusion without deciding the answer in advance"
    ),
    "data": (
        "requires corrupting or destroying real data to reproduce, which is not an "
        "acceptable thing for a benchmark to do to a stack it does not own"
    ),
    "migration": (
        "requires a database carrying schema state; the reference stack is stateless"
    ),
    "load": "requires a load generator, which is not built yet",
    "application": (
        "requires instrumented application code; the reference stack reports "
        "orchestration state only"
    ),
}


def _recreate(service: str, ns: str, stack: EphemeralStack) -> None:
    """Force the Recreate strategy before damaging a deployment.

    Under the default RollingUpdate the old ReplicaSet keeps serving until the
    new pods are ready, so a broken image, a broken entrypoint and an
    unschedulable pod spec all leave availability at 100% — the fault exists in
    the spec and never reaches the state anything can observe. Every damaging
    injector was silently a no-op because of this, and the arms were being
    graded for missing faults that had not happened yet.
    """
    kubectl(
        "patch", f"deployment/{service}", "-n", ns, "--type=json",
        "-p", '[{"op":"replace","path":"/spec/strategy",'
              '"value":{"type":"Recreate"}}]',
        context=stack.context,
    )


@dataclass(frozen=True)
class Injection:
    """What was done to the stack, and how to describe it in the record."""

    describe: str
    target: str


def target_for(scenario: PibScenario) -> str:
    """Pick a service deterministically, so a rerun of a scenario hits the same one."""
    if scenario.fault.target in SERVICES:
        return scenario.fault.target
    return SERVICES[sum(ord(c) for c in scenario.id) % len(SERVICES)]


def excluded_reason(scenario: PibScenario) -> str | None:
    """Why this scenario cannot be run here, or None if it can."""
    if reason := UNSUPPORTED.get(scenario.fault.type):
        return f"fault type {scenario.fault.type!r}: {reason}"

    unmeasurable = [
        key for key in scenario.expected.recovery_state if key not in OBSERVABLE
    ]
    if unmeasurable:
        return (
            f"recovery condition needs {sorted(unmeasurable)}, which this stack "
            f"cannot report; it observes only {list(OBSERVABLE)}"
        )
    return None


def inject(scenario: PibScenario, stack: EphemeralStack) -> Injection:
    """Create the fault. Raises if the scenario should have been excluded."""
    reason = excluded_reason(scenario)
    if reason is not None:
        raise ValueError(f"{scenario.id} is not injectable here — {reason}")

    service = target_for(scenario)
    ns = stack.namespace
    kind = scenario.fault.type

    if scenario.outcome is Outcome.NOTHING:
        # A negative scenario is benign activity by definition, whatever category
        # its fault type names. Dispatching on the type alone genuinely broke the
        # stack for a case whose answer key says do nothing, which made those
        # scenarios unwinnable — the arm saw real damage and was graded wrong for
        # responding to it. The whole point of a negative is that it *looks* like
        # something and is not.
        kubectl(
            "scale", f"deployment/{service}", "--replicas=3",
            "-n", ns, context=stack.context,
        )
        return Injection(
            f"benign {kind} activity on {service} (visible, expected, not a fault)", service
        )

    if kind == "deployment":
        _recreate(service, ns, stack)
        # A tag that cannot be pulled: real ImagePullBackOff, real unavailable
        # replicas, and a real rollback target in the revision history.
        kubectl(
            "set", "image", f"deployment/{service}", f"{service}={BROKEN_IMAGE}",
            "-n", ns, context=stack.context,
        )
        return Injection(f"set {service} to an unpullable image", service)

    if kind == "config":
        _recreate(service, ns, stack)
        # Overriding the entrypoint with something that does not exist. Setting
        # an env var was the obvious choice and was a no-op — a pause container
        # ignores it, the rollout succeeded, and the stack stayed healthy while
        # the harness recorded the arm as having missed a fault that was never
        # actually injected.
        kubectl(
            "patch", f"deployment/{service}", "-n", ns, "--type=json",
            "-p", '[{"op":"add","path":"/spec/template/spec/containers/0/command",'
                  '"value":["/pib-config-regression"]}]',
            context=stack.context,
        )
        return Injection(f"applied a config regression to {service} (bad entrypoint)", service)

    if kind == "scaling":
        kubectl(
            "scale", f"deployment/{service}", "--replicas=0",
            "-n", ns, context=stack.context,
        )
        return Injection(f"scaled {service} to zero", service)

    if kind == "dependency":
        upstream = SERVICES[(SERVICES.index(service) + 1) % len(SERVICES)]
        kubectl(
            "scale", f"deployment/{upstream}", "--replicas=0",
            "-n", ns, context=stack.context,
        )
        return Injection(f"took {service}'s dependency {upstream} offline", upstream)

    if kind == "infrastructure":
        _recreate(service, ns, stack)
        # Pinned to a node that does not exist, so the pods stay Pending.
        # Deleting them instead was self-healing: the deployment replaced them
        # within seconds and the stack was back to full health before anything
        # sampled it.
        kubectl(
            "patch", f"deployment/{service}", "-n", ns, "--type=json",
            "-p", '[{"op":"add","path":"/spec/template/spec/nodeSelector",'
                  '"value":{"pib/unschedulable":"true"}}]',
            context=stack.context,
        )
        return Injection(f"made {service} pods unschedulable", service)

    if kind in ("scheduled", "diurnal"):
        # Reached only by a non-negative scenario of this type. Benign either
        # way, but the stack is still disturbed rather than left idle — a
        # harness that injected nothing would be testing an idle cluster.
        kubectl(
            "scale", f"deployment/{service}", "--replicas=3",
            "-n", ns, context=stack.context,
        )
        return Injection(f"benign load change on {service} (expected activity)", service)

    raise ValueError(f"{scenario.id}: no injector for fault type {kind!r}")
