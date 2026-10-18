"""Train and test Shailaputri v0 on NAB's real series, against the statistical four.

    python -m sati.detect.run --cache .cache/nab --out results/shailaputri

**Leave one family out.** NAB's real series come in five families — AWS
CloudWatch, ad exchange, known-cause failures, traffic, tweets. Each family is
held out in turn: trained on the other four, its threshold chosen on those four
only, tested on the held-out family alongside the four statistical strategies
on exactly the same series. A detector scored on the kind of system it trained
on has learned the system.

Reported per family and as the mean across families: episode recall, precision,
F1, false alarms per 1000 points (the number an operator feels) and lead (how
early within the window the first flag came). F1 alone is not the claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import lightgbm as lgb
from pashupatastra.evaluation import Series, evaluate
from pashupatastra.strategies import Ewma, RobustZScore, SeasonalNaive, SeasonalRobustZ

from sati.detect import features as feats
from sati.detect import model
from sati.sources import nab

STATISTICAL = (RobustZScore, Ewma, SeasonalNaive, SeasonalRobustZ)
METRICS = ("precision", "recall", "f1", "false_alarms_per_1000", "mean_lead")


def load(cache: Path, rev: str) -> list[dict]:
    rows = []
    for name, wins in sorted(nab.windows(cache, rev).items()):
        frame = nab.series(name, cache, rev)
        values = frame["value"].to_numpy(dtype=float)
        ranges = nab.labelled_ranges(frame, wins)
        rows.append({
            "name": name,
            "family": name.split("/")[0],
            "values": values,
            "ranges": ranges,
            "features": feats.features(values),
            "labels": feats.labels(len(values), ranges),
        })
    return rows


def mean(rows: list[dict], key: str) -> float:
    vals = [float(r[key]) for r in rows]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def choose_threshold(booster: lgb.Booster, train: list[dict]) -> float:
    """The threshold with the best mean F1 on training series — never the test."""
    probs = [model.probabilities(booster, s["features"]) for s in train]
    best, best_f1 = model.THRESHOLDS[0], -1.0
    for t in model.THRESHOLDS:
        f1s = [
            evaluate(model.Replay(p, t), Series(s["name"], list(s["values"]), s["ranges"])).f1
            for s, p in zip(train, probs, strict=True)
        ]
        f1 = sum(f1s) / len(f1s)
        if f1 > best_f1:
            best, best_f1 = t, f1
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/nab"))
    parser.add_argument("--out", type=Path, default=Path("results/shailaputri"))
    parser.add_argument("--revision", default=None)
    args = parser.parse_args()

    started = time.time()
    rev = args.revision or nab.revision()
    data = load(args.cache, rev)
    families = sorted({s["family"] for s in data})
    print(f"NAB @ {rev[:12]} — {len(data)} real series in {len(families)} families")

    folds = []
    for held in families:
        train = [s for s in data if s["family"] != held]
        test = [s for s in data if s["family"] == held]
        assert not {s["name"] for s in train} & {s["name"] for s in test}
        booster = model.train([s["features"] for s in train], [s["labels"] for s in train])
        threshold = choose_threshold(booster, train)

        per_detector: dict[str, list[dict]] = {}
        for s in test:
            series = Series(s["name"], list(s["values"]), s["ranges"])
            p = model.probabilities(booster, s["features"])
            per_detector.setdefault("shailaputri-v0", []).append(evaluate(model.Replay(p, threshold), series).row())
            for factory in STATISTICAL:
                row = evaluate(factory(), series).row()
                per_detector.setdefault(row["strategy"], []).append(row)

        summary = {name: {m: mean(rows, m) for m in METRICS} for name, rows in per_detector.items()}
        folds.append({
            "held_out": held,
            "series": len(test),
            "train_series": len(train),
            "threshold": threshold,
            "detectors": summary,
        })
        line = "  ".join(f"{k} F1 {v['f1']:.3f}/FA {v['false_alarms_per_1000']:.1f}" for k, v in summary.items())
        print(f"  {held:18} {line}")

    detectors = list(folds[0]["detectors"]) if folds else []
    overall = {d: {m: round(sum(f["detectors"][d][m] for f in folds) / len(folds), 3) for m in METRICS} for d in detectors}

    # The model that would serve: trained on every real family.
    final = model.train([s["features"] for s in data], [s["labels"] for s in data])
    final_threshold = choose_threshold(final, data)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "shailaputri-v0.txt"
    final.save_model(str(path))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (args.out / "shailaputri-v0.meta.json").write_text(json.dumps({
        "model": "sati-shailaputri-v0", "sha256": digest, "threshold": final_threshold,
        "features": list(data[0]["features"].columns), "trained_on": {"dataset": "NAB", "revision": rev, "series": len(data)},
        "lightgbm": lgb.__version__, "python": platform.python_version(),
    }, indent=2) + "\n", encoding="utf-8")

    results = {
        "model": "sati-shailaputri-v0",
        "dataset": {"name": "NAB (real series only)", "repo": nab.REPO, "revision": rev,
                    "series": len(data), "families": families},
        "params": {"model": model.PARAMS, "rounds": model.ROUNDS, "thresholds": list(model.THRESHOLDS)},
        "folds": folds,
        "mean_across_families": overall,
        "model_sha256": digest,
        "seconds": round(time.time() - started, 1),
    }
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"done in {results['seconds']}s — model {digest[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
