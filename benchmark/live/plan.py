"""The pre-declared plan: which fault goes where, fixed before any incident is run.

    python -m benchmark.live.plan          # write plan.json
    python -m benchmark.live.plan --check  # fail if plan.json was edited

The four faults are none of PIB's (deployment, config, scaling, dependency,
infrastructure), so the set cannot overlap the PIB test set (RP-19):

* **cpu:** two busy processes started inside the root's container, against its CPU limit.
* **mem:** a process inside the root's container that grows to about 180 MB and holds it.
* **delay:** 400 ms added to every request the root serves.
* **release:** a new release of the root that fails 30% of its requests. It
  rolls out as a real Kubernetes deployment, so a deploy event is observable.

The root is drawn uniformly from all eight services with a fixed seed. Each
fault is used 50 times. The SHA-256 over the plan is recorded, so a plan
changed after results exist is visible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from .topology import SERVICES

PLAN = Path(__file__).with_name("plan.json")
FAULTS = ("cpu", "mem", "delay", "release")
N, SEED = 200, 19


def make() -> list[dict[str, str]]:
    rng = random.Random(SEED)
    return [{"id": f"live-{i:03d}", "fault": FAULTS[i % len(FAULTS)], "root": rng.choice(SERVICES)}
            for i in range(N)]


def digest(incidents: list[dict[str, str]]) -> str:
    return hashlib.sha256("\n".join(json.dumps(x, sort_keys=True) for x in incidents).encode()).hexdigest()


def load(path: Path = PLAN) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if digest(plan["incidents"]) != plan["sha256"]:
        raise ValueError(f"{path}: the incident list no longer matches its declared hash")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    incidents = make()
    plan = {"seed": SEED, "n": N, "faults": list(FAULTS), "services": SERVICES,
            "sha256": digest(incidents), "incidents": incidents}
    text = json.dumps(plan, indent=1) + "\n"
    if args.check:
        same = PLAN.exists() and PLAN.read_text(encoding="utf-8").replace("\r\n", "\n") == text
        print("same" if same else "DIFFERS")
        return 0 if same else 1
    PLAN.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
