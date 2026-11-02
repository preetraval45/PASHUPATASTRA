"""Automatic period detection, checked on NAB's real labelled series before anyone relies on it.

    python -m sati.seasonal.run --cache .cache/nab --out results/auto-seasonal

The Seasonality ADR kept seasonal detection opt-in because a wrong period makes a detector
blind, and said automatic detection was owed only once it could be validated on labelled data.
This is that check. On every real NAB series, three detectors from core run on exactly the same
values and are scored by the core harness, episode by episode:

- `robust-z`, the shipped default;
- `auto-seasonal`, told nothing: it finds the period itself (`pashupatastra.period`) or stays
  robust-z;
- `seasonal-robust-z` at a fixed day (288 five-minute samples), what a person opting a metric in
  without measuring it would most likely choose.

The question is the ADR's, so the first number is the one that would forbid shipping it: on how
many series does auto-seasonal miss an episode robust-z caught? Then false alarms, F1 and recall,
the mean per family and then across families, as `sati.detect.run` reports Shailaputri. Nothing
is trained, so there is nothing to hold out; the detectors only ever see each series once,
online, in time order.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pashupatastra.evaluation import Series, evaluate
from pashupatastra.strategies import AutoSeasonal, RobustZScore, SeasonalRobustZ

from sati.sources import nab

DAY = 288
METRICS = ("precision", "recall", "f1", "false_alarms_per_1000", "mean_lead")
DETECTORS = {
    "robust-z": lambda: RobustZScore(),
    "auto-seasonal": lambda: AutoSeasonal(),
    "seasonal-robust-z@288": lambda: SeasonalRobustZ(period=DAY),
}


def score_series(name: str, values: list[float], ranges: list[tuple[int, int]]) -> dict:
    series = Series(name, values, ranges)
    scores = {}
    auto = None
    for label, make in DETECTORS.items():
        detector = make()
        scores[label] = evaluate(detector, series)
        if label == "auto-seasonal":
            auto = detector
    return {
        "name": name,
        "family": name.split("/")[0],
        "samples": len(values),
        "episodes": len(ranges),
        "period": auto.period if auto else None,
        "caught": {label: s.caught_episodes for label, s in scores.items()},
        "rows": {label: {m: s.row()[m] for m in METRICS} for label, s in scores.items()},
    }


def mean(values: list[float]) -> float:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/nab"))
    parser.add_argument("--out", type=Path, default=Path("results/auto-seasonal"))
    parser.add_argument("--revision", default=None)
    args = parser.parse_args()

    started = time.time()
    rev = args.revision or nab.revision()
    rows = []
    for name, wins in sorted(nab.windows(args.cache, rev).items()):
        frame = nab.series(name, args.cache, rev)
        values = [float(v) for v in frame["value"].to_numpy(dtype=float)]
        rows.append(score_series(name, values, nab.labelled_ranges(frame, wins)))
        last = rows[-1]
        print(f"  {name:60} period {last['period']}  caught {last['caught']}")

    families = sorted({r["family"] for r in rows})
    by_family = {
        family: {
            label: {m: mean([r["rows"][label][m] for r in rows if r["family"] == family]) for m in METRICS}
            for label in DETECTORS
        }
        for family in families
    }
    overall = {
        label: {m: mean([by_family[f][label][m] for f in families]) for m in METRICS} for label in DETECTORS
    }
    switched = [r for r in rows if r["period"] is not None]
    blinded = [r["name"] for r in rows if r["caught"]["auto-seasonal"] < r["caught"]["robust-z"]]
    gained = [r["name"] for r in rows if r["caught"]["auto-seasonal"] > r["caught"]["robust-z"]]

    results = {
        "experiment": "auto-seasonal on NAB",
        "dataset": {"name": "NAB (real series only)", "repo": nab.REPO, "revision": rev,
                    "series": len(rows), "families": families},
        "detectors": list(DETECTORS),
        "summary": {
            "series_with_a_period": len(switched),
            "periods_found": sorted({r["period"] for r in switched}),
            "episodes": sum(r["episodes"] for r in rows),
            "caught": {label: sum(r["caught"][label] for r in rows) for label in DETECTORS},
            "series_where_auto_missed_what_robust_z_caught": blinded,
            "series_where_auto_caught_what_robust_z_missed": gained,
        },
        "mean_across_families": overall,
        "by_family": by_family,
        "series": rows,
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    print(f"done in {results['seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
