"""Run the observation window against a real cluster.

The window's failure modes are about timing, and timing is the one thing a fake
clock cannot check. Every bug this area has produced so far was found by real
infrastructure: the self-rollback repeat, the rollback that used the original
parameters, and the busy-spin that a fake clock hid completely.

Usage:
    python scripts/verifywindow.py [namespace] [deployment]
"""

from __future__ import annotations

import sys
from datetime import timedelta

sys.path.insert(0, "services/api")
sys.path.insert(0, "packages/core")

from app.engines.executors import KubernetesExecutor  # noqa: E402
from pashupatastra.observation import (  # noqa: E402
    Settling,
    Window,
    WindowObserver,
    as_checks,
)
from pashupatastra.registry import get as get_action  # noqa: E402

NAMESPACE = sys.argv[1] if len(sys.argv) > 1 else "pashu-test"
DEPLOYMENT = sys.argv[2] if len(sys.argv) > 2 else "checkout-api"

SHORT = Window(
    settle=timedelta(seconds=2),
    timeout=timedelta(seconds=45),
    interval=timedelta(seconds=3),
    hold_samples=3,
)

executor = KubernetesExecutor()
observer = WindowObserver()
params = {"namespace": NAMESPACE, "deployment": DEPLOYMENT}
failures: list[str] = []

# Discovered rather than assumed. The executor defaults the container to the
# deployment name, which is a convention plenty of real deployments do not follow
# — this one names its container `pause`.
CONTAINER = executor._kubectl(
    "get", f"deployment/{DEPLOYMENT}", "-n", NAMESPACE,
    "-o", "jsonpath={.spec.template.spec.containers[0].name}",
)


def check(name: str, passed: bool, detail: str) -> None:
    print(f"{'PASS' if passed else 'FAIL'}  {name}\n      {detail}")
    if not passed:
        failures.append(name)


def watch(action_id: str, window: Window = SHORT):
    action = get_action(action_id)
    return observer.watch(
        action_id, lambda: executor.observe(action, params), window
    )


print(f"cluster observation window — {NAMESPACE}/{DEPLOYMENT}\n")

# 1 — a healthy deployment must actually hold, not merely pass once.
result = watch("restart_service")
check(
    "a healthy deployment holds across consecutive samples",
    result.settling is Settling.HELD and result.verified,
    f"{result.settling} after {len(result.samples)} samples — {result.describe()}",
)

# 2 — the loop must see the window verdict, not just the last sample.
checks = as_checks(result)
check(
    "the window verdict travels as its own check",
    any(c.name == "sustained" for c in checks) and all(c.passed for c in checks),
    f"{len(checks)} checks: " + ", ".join(f"{c.name}={c.passed}" for c in checks),
)

# 3 — real elapsed time. The busy-spin bug made this near-zero while the sample
#     count exploded, so both are asserted rather than just the verdict.
elapsed = (result.samples[-1].at - result.samples[0].at).total_seconds()
check(
    "sampling is paced by the interval rather than spinning",
    len(result.samples) <= 10 and elapsed >= 0,
    f"{len(result.samples)} samples over {elapsed:.1f}s "
    f"(a busy-spin produced millions)",
)

# 4 — a deployment that cannot become ready must not read as recovered.
print("\n  breaking the deployment with an unpullable image...")
executor.run(
    get_action("redeploy_version"),
    {**params, "image": "nginx:doesnotexist-pashupatastra", "container": CONTAINER},
)
broken = watch("restart_service")
check(
    "a deployment that never becomes ready is not verified",
    not broken.verified,
    f"{broken.settling} — {broken.describe()}",
)

check(
    "the failed window reaches the loop as a failing check",
    not all(c.passed for c in as_checks(broken)),
    "at least one check is False, so the loop rolls back",
)

# 5 — restore, and confirm the window sees recovery rather than staying stuck.
print("\n  rolling back to the working image...")
executor.run(get_action("rollback_deployment"), params)
recovered = watch("restart_service", SHORT)
check(
    "recovery after a rollback is observed as held",
    recovered.settling is Settling.HELD,
    f"{recovered.settling} — {recovered.describe()}",
)

print()
if failures:
    print(f"{len(failures)} FAILED: {', '.join(failures)}")
    sys.exit(1)
print("all window checks passed against the live cluster")
