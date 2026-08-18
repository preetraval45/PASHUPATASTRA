"""The reference stack, and the ephemeral namespace it runs in.

One namespace per run, torn down afterwards. Not for tidiness: a scenario that
inherits the previous scenario's broken deployment produces a result about the
wrong fault, and nothing in the output would say so.
"""

from __future__ import annotations

import subprocess
import time

NAMESPACE_PREFIX = "pib"
IMAGE = "registry.k8s.io/pause:3.10"
REPLICAS = 2

# Five services with a dependency order, matching `reference-5svc` in the
# scenarios. Names are what the injectors and the action parameters refer to.
SERVICES = ("gateway", "checkout", "pricing", "inventory", "notifier")
DEPENDS_ON = {
    "gateway": "checkout",
    "checkout": "pricing",
    "pricing": "inventory",
    "inventory": None,
    "notifier": None,
}


class StackError(RuntimeError):
    pass


def kubectl(*args: str, context: str | None = None, timeout: float = 60.0) -> str:
    command = ["kubectl"]
    if context:
        command += ["--context", context]
    command += list(args)
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise StackError(f"{' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def manifest(namespace: str) -> str:
    parts = [
        f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {namespace}\n",
    ]
    for service in SERVICES:
        parts.append(
            f"""---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service}
  namespace: {namespace}
  labels: {{app: {service}, stack: reference-5svc}}
spec:
  replicas: {REPLICAS}
  selector:
    matchLabels: {{app: {service}}}
  template:
    metadata:
      labels: {{app: {service}}}
    spec:
      terminationGracePeriodSeconds: 0
      containers:
        - name: {service}
          image: {IMAGE}
          env:
            - name: DEPENDS_ON
              value: "{DEPENDS_ON[service] or ''}"
          resources:
            requests: {{cpu: 5m, memory: 16Mi}}
            limits: {{cpu: 100m, memory: 64Mi}}
"""
        )
    return "".join(parts)


class EphemeralStack:
    """A namespace holding one run's copy of the reference stack.

    Use as a context manager. Teardown runs on the way out whether the body
    succeeded, raised, or was interrupted — a leaked namespace silently changes
    what every later run in the same cluster is measuring.
    """

    def __init__(self, run_id: str, context: str | None = None, wait: float = 90.0) -> None:
        self.namespace = f"{NAMESPACE_PREFIX}-{run_id}"
        self.context = context
        self.wait = wait

    def __enter__(self) -> "EphemeralStack":
        self.up()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.down()

    def up(self) -> None:
        # Teardown does not block, so a namespace from a previous run of the same
        # scenario may still be Terminating. Applying into one fails, and the
        # failure would be recorded as a harness error on a rig that is actually
        # fine — just impatient.
        self._await_gone()
        subprocess.run(
            ["kubectl"]
            + (["--context", self.context] if self.context else [])
            + ["apply", "-f", "-"],
            input=manifest(self.namespace),
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        self._await_ready()

    def _await_gone(self, timeout: float = 60.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                kubectl(
                    "get", "namespace", self.namespace, "-o", "jsonpath={.status.phase}",
                    context=self.context,
                )
            except StackError:
                return  # absent, which is what we want
            time.sleep(2)
        raise StackError(
            f"{self.namespace}: a namespace from a previous run is still terminating "
            f"after {timeout}s"
        )

    def _await_ready(self) -> None:
        deadline = time.monotonic() + self.wait
        while time.monotonic() < deadline:
            if all(self.ready(service) >= 1 for service in SERVICES):
                return
            time.sleep(2)
        raise StackError(
            f"{self.namespace}: the stack did not become ready within {self.wait}s — "
            "a run starting from a broken baseline measures the baseline, not the fault"
        )

    def down(self) -> None:
        try:
            kubectl(
                "delete", "namespace", self.namespace, "--wait=false", "--ignore-not-found",
                context=self.context,
            )
        except Exception as error:  # noqa: BLE001
            # Loud rather than swallowed. A namespace that outlives its run
            # poisons later runs, and a quiet teardown failure is how a whole
            # afternoon of results turns out to have been measuring leftovers.
            print(f"  TEARDOWN FAILED for {self.namespace}: {error}")
            raise

    def ready(self, service: str) -> int:
        try:
            value = kubectl(
                "get", f"deployment/{service}", "-n", self.namespace,
                "-o", "jsonpath={.status.readyReplicas}",
                context=self.context,
            )
        except StackError:
            return 0
        return int(value) if value.isdigit() else 0

    def desired(self, service: str) -> int:
        value = kubectl(
            "get", f"deployment/{service}", "-n", self.namespace,
            "-o", "jsonpath={.spec.replicas}",
            context=self.context,
        )
        return int(value) if value.isdigit() else 0

    def restarts(self, service: str) -> int:
        value = kubectl(
            "get", "pods", "-n", self.namespace, "-l", f"app={service}",
            "-o", "jsonpath={.items[*].status.containerStatuses[*].restartCount}",
            context=self.context,
        )
        return sum(int(v) for v in value.split() if v.isdigit())

    def unhealthy_services(self) -> list[str]:
        """Services below their baseline replica count.

        Discovered from the cluster rather than told to the arm — which service
        is broken is an observation, and handing it over would be part of the
        answer key.
        """
        return [s for s in SERVICES if self.ready(s) < REPLICAS]

    def observe(self) -> dict[str, float]:
        """The state this stack can actually report.

        Deliberately short. Every scenario whose recovery condition needs
        something outside this dictionary is excluded by name and by reason
        rather than graded on a substitute — a benchmark that swaps in a metric
        it can measure for the one the scenario named is measuring something
        nobody chose.
        """
        ready = sum(self.ready(s) for s in SERVICES)
        # Measured against the baseline the stack was built with, not against
        # the current spec. ready/desired is blind to the fault that matters
        # most here: scaling a service to zero drops both halves of the ratio
        # and reports 100% availability for a service that is entirely gone.
        return {
            "ready_replicas": float(ready),
            "restarts": float(sum(self.restarts(s) for s in SERVICES)),
            "availability": round(min(100.0, 100.0 * ready / BASELINE_READY), 2),
        }


BASELINE_READY = len(SERVICES) * REPLICAS
"""What a healthy stack reports. Availability is relative to this."""

OBSERVABLE = ("ready_replicas", "restarts", "availability")
"""Recovery-state keys this stack can grade. See `EphemeralStack.observe`."""
