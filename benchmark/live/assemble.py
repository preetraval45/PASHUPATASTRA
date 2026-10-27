"""Merge the shards' records into the committed dataset.

    python -m benchmark.live.assemble live-out benchmark/live/dataset

Writes `incidents.jsonl.gz`, one record per planned incident in plan order,
and `meta.json` with the plan's hash, the call graph and what failed. An
incident that errored stays in the list as an error, so a failure cannot
quietly shrink the denominator.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

from .plan import load
from .topology import GRAPH, SERVICES


def main(src: str, dst: str) -> int:
    plan = load()
    out = Path(dst)
    out.mkdir(parents=True, exist_ok=True)
    records, missing = [], []
    for inc in plan["incidents"]:
        found = list(Path(src).rglob(f"{inc['id']}.json"))
        if not found:
            missing.append(inc["id"])
            records.append({**inc, "error": "no record: the shard did not finish"})
            continue
        records.append(json.loads(found[0].read_text(encoding="utf-8")))
    with gzip.open(out / "incidents.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    errors = {r["id"]: r["error"][:200] for r in records if "error" in r}
    meta = {"plan_sha256": plan["sha256"], "services": SERVICES, "graph": GRAPH,
            "incidents": len(records), "errors": errors}
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(f"{len(records)} incidents, {len(errors)} errors, {len(missing)} missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
