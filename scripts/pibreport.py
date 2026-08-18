"""Produce the PIB metrics table from the run records.

    python scripts/pibreport.py

Reads `benchmark/results/**/*.jsonl` and nothing else. It never imports the
harness or re-runs anything, which is the point: METRICS.md requires every
number to be recomputable by someone else from the record, and a reporter that
could reach into the harness would not prove that.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "packages/core")

from pashupatastra.metrics import (  # noqa: E402
    NOT_COMPUTABLE,
    compute,
    duration_spread,
    load_records,
    per_scenario,
)

RESULTS = Path(sys.argv[1] if len(sys.argv) > 1 else "benchmark/results")


def exclusions_for(directory: Path, suffix: str) -> list[dict]:
    path = directory / f"exclusions{suffix}.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    files = sorted(RESULTS.glob("**/runs*.jsonl"))
    if not files:
        print(f"no run records under {RESULTS}. Run the harness first:")
        print("  python -m benchmark.harness.run --arm pashupatastra")
        return 1

    print(f"PIB metrics — recomputed from {len(files)} run record(s)\n")

    for file in files:
        records = load_records(file)
        if not records:
            continue
        metrics = compute(records)
        suffix = file.stem.replace("runs", "")
        label = f"{metrics.arm}" + (f" [{metrics.ablation}]" if metrics.ablation != "none" else "")

        print("=" * 66)
        print(f"{label}   ({file})")
        print("=" * 66)
        for name, value in metrics.table():
            print(f"  {name:<34} {value}")

        if metrics.by_cause:
            # METRICS.md: the breakdown is more informative than the aggregate,
            # because it shows *where* autonomy stops.
            print("\n  where autonomy stopped:")
            for cause, count in sorted(metrics.by_cause.items(), key=lambda kv: -kv[1]):
                print(f"    {cause:<28} {count}")

        mean, stdev = duration_spread(records)
        print(f"\n  run duration                       mean {mean}s, sd {stdev}s")

        rows = per_scenario(records)
        unstable = [r for r in rows if r.unstable]
        print(f"\n  per scenario ({len(rows)} run, {len(unstable)} unstable):")
        for row in rows:
            mark = "  UNSTABLE" if row.unstable else ""
            print(f"    {row.scenario_id}  {row.outcome:<10} {row.correct}/{row.runs}"
                  f"  {row.verdicts}{mark}")

        excluded = exclusions_for(file.parent, suffix)
        print(f"\n  excluded from this table: {len(excluded)}")
        reasons: dict[str, int] = {}
        for entry in excluded:
            reason = entry["reason"]
            # Grouped on a stable head. Splitting on punctuation put the same
            # reason under several keys whenever the metric list ran long.
            if reason.startswith("recovery condition"):
                head = "recovery condition needs a metric this stack cannot report"
            elif reason.startswith("fault type"):
                head = reason.split(":")[0]
            else:
                head = reason.split(":")[0].split(",")[0]
            reasons[head] = reasons.get(head, 0) + 1
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"    {count:>3}  {reason}")

        covered = len(rows)
        total = covered + len(excluded)
        print(f"\n  coverage: {covered}/{total} scenarios "
              f"({round(100 * covered / total) if total else 0}%)")
        print()

    # Printed once, at the end, and never omitted. A table showing five of the
    # eight metrics METRICS.md defines, with no note, reads as a complete table.
    print("=" * 66)
    print("NOT COMPUTED — defined in METRICS.md, not derivable from these records")
    print("=" * 66)
    for metric, reason in NOT_COMPUTABLE.items():
        print(f"  {metric}")
        for line in _wrap(reason, 62):
            print(f"      {line}")
    return 0


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
