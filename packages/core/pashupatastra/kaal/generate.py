"""Write a Kaal dataset: one labelled incident per JSON line (RP-17).

    python -m pashupatastra.kaal.generate --n 1000 --seed 1 --out data/kaal-1.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pashupatastra.kaal.generator import VERSION, incident


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("kaal.jsonl"))
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    outcomes: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    with args.out.open("w", encoding="utf-8") as handle:
        for i in range(args.n):
            inc = incident(args.seed, i)
            outcomes[str(inc.label["outcome"])] += 1
            categories[str(inc.label["category"])] += 1
            handle.write(json.dumps(inc.to_json(), separators=(",", ":")) + "\n")
    print(f"{VERSION}: {args.n} incidents, seed {args.seed} → {args.out}")
    print(f"  outcomes   {dict(sorted(outcomes.items()))}")
    print(f"  categories {dict(sorted(categories.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
