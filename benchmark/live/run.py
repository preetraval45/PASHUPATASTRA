"""Run a shard of the pre-declared plan on a kind cluster (RP-19).

    python -m benchmark.live.run --shard 3 --shards 20 --out live-out

Each incident gets a fresh namespace holding the whole stack. A fault left over
from the previous incident would be recorded against the wrong one, which is
what PIB's harness learned (benchmark/harness/stack.py). Timeline:

1. apply, then wait for every deployment to be available;
2. warm up, so the first rates are not a cold start;
3. baseline, then inject the planned fault at the root, and observe;
4. keep the collector's lines and the stack's ReplicaSet creation times,
   then delete the namespace.

Written per incident: the collector's samples (what a model may see), the
ReplicaSets (deploy events, also observable), and the plan's answer. The
answer is stored in the record so the scorer can find it, and `sati.rca.live`
joins it on only after the features are built.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .plan import load
from .topology import SERVICES, manifest

WARMUP, BASELINE, OBSERVE = 40, 120, 150

MEM_HOG = (
    "import time\nb=[]\nfor _ in range(45):\n    b.append(bytearray(b'x'*4194304))\n    time.sleep(1)\n"
    "time.sleep(100000)\n"
)


def kubectl(*args: str, stdin: str | None = None, timeout: float = 240) -> str:
    done = subprocess.run(["kubectl", *args], input=stdin, capture_output=True, text=True, timeout=timeout)
    if done.returncode:
        raise RuntimeError(f"kubectl {' '.join(args[:3])} failed: {done.stderr.strip()[:400]}")
    return done.stdout


def inject(fault: str, root: str, ns: str) -> str:
    """Create the fault from outside the service, as a chaos tool would."""
    if fault == "cpu":
        kubectl("exec", "-n", ns, f"deploy/{root}", "--", "sh", "-c",
                "for i in 1 2; do nohup python3 -c 'while True: pass' >/dev/null 2>&1 & done")
        return f"two busy processes in {root}'s container"
    if fault == "mem":
        kubectl("exec", "-n", ns, f"deploy/{root}", "--", "sh", "-c",
                f"nohup python3 -c \"{MEM_HOG}\" >/dev/null 2>&1 &")
        return f"a process in {root}'s container growing to ~180 MB"
    if fault == "delay":
        kubectl("exec", "-n", ns, f"deploy/{root}", "--", "python3", "-c",
                "import urllib.request; urllib.request.urlopen('http://localhost:8080/fault?delay_ms=400')")
        return f"400 ms added to every request {root} serves"
    if fault == "release":
        kubectl("set", "env", f"deployment/{root}", "-n", ns, "RELEASE=bad")
        return f"a release of {root} that fails 30% of requests"
    raise ValueError(fault)


def replicasets(ns: str) -> dict[str, list[int]]:
    """Each service's ReplicaSet creation times (unix seconds): its deploy events."""
    out: dict[str, list[int]] = {}
    for rs in json.loads(kubectl("get", "rs", "-n", ns, "-o", "json"))["items"]:
        app = rs["metadata"].get("labels", {}).get("app")
        if app in SERVICES:
            t = datetime.fromisoformat(rs["metadata"]["creationTimestamp"].replace("Z", "+00:00"))
            out.setdefault(app, []).append(int(t.timestamp()))
    return {k: sorted(v) for k, v in out.items()}


def run_one(inc: dict[str, str]) -> dict:
    ns = inc["id"]
    kubectl("apply", "-f", "-", stdin=manifest(ns))
    try:
        kubectl("wait", "--for=condition=available", "deployment", "--all", "-n", ns, "--timeout=240s", timeout=260)
        time.sleep(WARMUP + BASELINE)
        inject_time = int(time.time())
        injected = inject(inc["fault"], inc["root"], ns)
        time.sleep(OBSERVE)
        lines = kubectl("logs", "-n", ns, "deploy/collector").splitlines()
        samples = [json.loads(x) for x in lines if x.startswith("{")]
        deploys = replicasets(ns)
    finally:
        subprocess.run(["kubectl", "delete", "namespace", ns, "--wait=false"], capture_output=True, check=False)
    return {**inc, "inject_time": inject_time, "window": {"before": BASELINE, "after": OBSERVE},
            "injected": injected, "deploys": deploys, "samples": samples}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--out", type=Path, default=Path("live-out"))
    parser.add_argument("--limit", type=int, default=0, help="incidents from this shard, for a smoke run")
    args = parser.parse_args()
    plan = load()
    mine = plan["incidents"][args.shard :: args.shards]
    if args.limit:
        mine = mine[: args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for inc in mine:
        started = time.time()
        try:
            record = run_one(inc)
        except Exception as exc:  # recorded, never dropped silently
            failed += 1
            record = {**inc, "error": str(exc)[:500]}
        (args.out / f"{inc['id']}.json").write_text(json.dumps(record) + "\n", encoding="utf-8")
        print(f"{inc['id']} {inc['fault']:8s} {inc['root']:8s} "
              f"{'ERROR ' + record['error'][:80] if 'error' in record else len(record['samples'])} "
              f"{time.time() - started:.0f}s", flush=True)
    return 1 if failed == len(mine) else 0


if __name__ == "__main__":
    raise SystemExit(main())
