"""Train and test Mahagauri v0: has the server really returned to normal?

    python -m sati.verify.run --cache .cache/smd --out results/mahagauri

Mahagauri is model 8 of the nine (adr/Navadurga). It does Verify, the step in
`Observe → … → Act → Verify → Learn` that decides whether an incident is over.
Engineering rule 3 makes verification compare observed state with expected
state; this model learns what "back to normal" looks like on real servers.

**The task.** SMD gives each of 28 real servers a labelled test period. For
every labelled anomaly, from its first minute until an hour after it ends (or
until the next anomaly starts), Mahagauri answers once a minute: recovered,
or not yet? It declares "all clear" at the first of three consecutive
recovered answers.

**What is measured, worst failure first:**

* **Premature all-clear:** the share of incidents declared over while still
  labelled anomalous. This is the dangerous error: an operator stands down
  while the fault continues.
* **Confirmation delay:** minutes from the true end to the all-clear, for
  incidents confirmed correctly. Lower is better.
* **Unconfirmed:** the share never declared over within the hour, which leaves
  a human to decide.

**Features at minute t.** These are Shailaputri's causal features aggregated
across metrics, plus each metric's distance from **its own pre-incident
baseline** (the hour before the anomaly began): the max, the mean, and the
count beyond 3. Minutes since onset are also used, which a deployed verifier
knows. Nothing is computed from after t.

**Split.** Leave one machine group out, as for Shailaputri v1. Thresholds are
chosen on the training groups. The rule: the lowest threshold whose premature
rate there stays at or below 5%.

**v2 (27 Oct).** v0 and v1 chose the threshold from the model's predictions
on its *own training data*, which are over-confident, so the threshold came out
too lenient and premature all-clears rose on unseen machines. v2 chooses on
**out-of-fold** predictions inside the training groups (each training group
predicted by a model fitted without it, as Siddhidatri does). It chooses the
**hold time** too (3, 5 or 10 consecutive recovered minutes). Among the
settings whose one-sided 95% upper bound on premature all-clears stays within
5%, it keeps the one that confirms the most recoveries.

**Baselines,** under the same three-in-a-row rule:

* **Back within 3σ:** all clear once no metric is more than 3 robust standard
  deviations from its pre-incident baseline. This is what a hand-written
  verification check amounts to.
* **Fixed timer:** all clear after the median anomaly length seen in training.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from sati.detect import model as detect_model
from sati.detect import smd as smd_run
from sati.sources import smd

HORIZON = 60  # minutes after the true end that a verifier is given to confirm
BASELINE = 60  # minutes before onset that define "normal" for this incident
CONSECUTIVE = 3
HOLDS = (3, 5, 10)
PREMATURE_BUDGET = 0.05
THRESHOLDS = tuple(round(t, 2) for t in np.arange(0.3, 0.99, 0.02))


def episodes(m: dict) -> list[dict]:
    """Every labelled anomaly with enough clean history before it, and the
    minutes a verifier would be asked about: onset to end + HORIZON, cut at the
    next anomaly. History before the test half comes from the train half."""
    ranges = smd.ranges(m["labels"])
    history = np.vstack([m["train"], m["test"]])
    offset = len(m["train"])
    out = []
    for i, (start, end) in enumerate(ranges):
        stop = min(end + HORIZON, ranges[i + 1][0] if i + 1 < len(ranges) else len(m["test"]))
        pre = history[offset + start - BASELINE : offset + start]
        if len(pre) < BASELINE or stop <= end:
            continue
        out.append({"machine": m["name"], "group": m["group"], "start": start, "end": end, "stop": stop,
                    "pre": pre, "window": m["test"][start:stop], "features": m["features"].iloc[start:stop]})
    return out


def baseline_distance(pre: np.ndarray, window: np.ndarray) -> np.ndarray:
    """|x - pre-incident median| / pre-incident robust scale, per minute and metric."""
    centre = np.median(pre, axis=0)
    q75, q25 = np.percentile(pre, [75, 25], axis=0)
    scale = (q75 - q25) / 1.349
    scale = np.where(scale > 0, scale, np.maximum(pre.std(axis=0), 1e-6))
    return np.abs(window - centre) / scale


def frame(ep: dict) -> pd.DataFrame:
    d = baseline_distance(ep["pre"], ep["window"])
    f = ep["features"].reset_index(drop=True).copy()
    f["pre_max"] = np.log1p(d.max(axis=1))
    f["pre_mean"] = np.log1p(d.mean(axis=1))
    f["pre_beyond_3"] = (d > 3).sum(axis=1).astype(float)
    f["minutes_since_onset"] = np.arange(len(d), dtype=float)
    return f


def trajectory(f: pd.DataFrame) -> pd.DataFrame:
    """v3: where the incident is heading, not only where it is. Each minute's
    distance from baseline is set against the incident's own peak so far, with
    the minutes since that peak, since any metric was last beyond 3, and the
    five-minute trend of the mean distance. All causal: minute t uses minutes
    up to t only."""
    out = f.copy()
    minutes = np.arange(len(f), dtype=float)
    peak = f["pre_max"].cummax()
    out["share_of_peak"] = f["pre_max"] / (peak + 1e-9)
    at_peak = np.where(f["pre_max"].to_numpy() >= peak.to_numpy(), minutes, np.nan)
    out["minutes_since_peak"] = minutes - pd.Series(at_peak).ffill().fillna(0).to_numpy()
    beyond = np.where(f["pre_beyond_3"].to_numpy() > 0, minutes, np.nan)
    out["minutes_since_beyond_3"] = minutes - pd.Series(beyond).ffill().fillna(-1).to_numpy()
    out["trend_5"] = f["pre_mean"] - f["pre_mean"].shift(5).fillna(f["pre_mean"].iloc[0] if len(f) else 0.0)
    return out


def labels(ep: dict) -> np.ndarray:
    return (np.arange(ep["stop"] - ep["start"]) >= ep["end"] - ep["start"]).astype(int)


def all_clear(recovered: np.ndarray, hold: int = CONSECUTIVE) -> int | None:
    """Index of the first minute ending `hold` consecutive recovered answers, or None."""
    run = 0
    for i, r in enumerate(recovered):
        run = run + 1 if r else 0
        if run >= hold:
            return i
    return None


def outcome(ep: dict, recovered: np.ndarray, hold: int = CONSECUTIVE) -> dict:
    declared = all_clear(recovered, hold)
    length = ep["end"] - ep["start"]
    if declared is None:
        return {"result": "unconfirmed"}
    if declared < length:
        return {"result": "premature", "early_by": int(length - declared)}
    return {"result": "confirmed", "delay": int(declared - length)}


def summary(outcomes: list[dict]) -> dict:
    n = len(outcomes)
    count = {k: sum(o["result"] == k for o in outcomes) for k in ("premature", "confirmed", "unconfirmed")}
    delays = [o["delay"] for o in outcomes if o["result"] == "confirmed"]
    return {
        "incidents": n,
        "premature_rate": round(count["premature"] / n, 4) if n else 0.0,
        "confirmed_rate": round(count["confirmed"] / n, 4) if n else 0.0,
        "unconfirmed_rate": round(count["unconfirmed"] / n, 4) if n else 0.0,
        "median_delay": float(np.median(delays)) if delays else None,
        "mean_delay": round(float(np.mean(delays)), 1) if delays else None,
    }


def wilson_upper(k: int, n: int, z: float = 1.645) -> float:
    """One-sided 95% upper bound on a rate from k events in n trials."""
    if n == 0:
        return 1.0
    p = k / n
    centre = p + z * z / (2 * n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return float((centre + half) / (1 + z * z / n))


def choose(train: list[dict], probs: list[np.ndarray], upper: bool = False,
           agree: list[np.ndarray] | None = None) -> float:
    """The lowest threshold that keeps premature all-clears within budget on
    the training groups; the strictest one if none does.

    v0 holds the *point estimate* within budget. On held-out groups that gave
    0.199, because a threshold chosen to sit exactly at 5% on one sample
    drifts above it on the next. `upper=True` holds the one-sided 95% upper
    bound within budget instead. `agree` adds a second condition that must
    also say "recovered" (the 3σ check)."""
    for t in THRESHOLDS:
        votes = [p >= t if agree is None else (p >= t) & a
                 for p, a in zip(probs, agree or [None] * len(probs), strict=True)]
        results = [outcome(ep, v) for ep, v in zip(train, votes, strict=True)]
        premature = sum(r["result"] == "premature" for r in results)
        rate = wilson_upper(premature, len(results)) if upper else premature / max(1, len(results))
        if rate <= PREMATURE_BUDGET:
            return t
    return THRESHOLDS[-1]


def fit(eps: list[dict], key: str = "frame") -> lgb.Booster:
    return lgb.train(detect_model.PARAMS, lgb.Dataset(pd.concat([ep[key] for ep in eps], ignore_index=True),
                                                    label=np.concatenate([ep["y"] for ep in eps])),
                     num_boost_round=detect_model.ROUNDS)


def out_of_fold(train: list[dict], key: str = "frame") -> list[np.ndarray]:
    """Each training incident scored by a model fitted without its machine group.

    With a single training group there is nothing to hold out, so the scores are
    in-sample (v0's behaviour); the full SMD run always has two."""
    if len({ep["group"] for ep in train}) < 2:
        model = fit(train, key)
        return [model.predict(ep[key]) for ep in train]
    probs: list[np.ndarray | None] = [None] * len(train)
    for g in sorted({ep["group"] for ep in train}):
        inner = fit([ep for ep in train if ep["group"] != g], key)
        for i, ep in enumerate(train):
            if ep["group"] == g:
                probs[i] = inner.predict(ep[key])
    return probs  # type: ignore[return-value]


def choose_v2(train: list[dict], probs: list[np.ndarray], agree: list[np.ndarray] | None = None
              ) -> tuple[float, int]:
    """(threshold, hold) whose upper-bound premature rate is within budget on
    out-of-fold scores and which confirms the most recoveries; the strictest
    setting if none is within budget."""
    best, best_confirmed = (THRESHOLDS[-1], HOLDS[-1]), -1.0
    for hold in HOLDS:
        for t in THRESHOLDS:
            votes = [p >= t if agree is None else (p >= t) & a
                     for p, a in zip(probs, agree or [None] * len(probs), strict=True)]
            results = [outcome(ep, v, hold) for ep, v in zip(train, votes, strict=True)]
            premature = sum(r["result"] == "premature" for r in results)
            if wilson_upper(premature, len(results)) > PREMATURE_BUDGET:
                continue
            confirmed = sum(r["result"] == "confirmed" for r in results) / len(results)
            if confirmed > best_confirmed:
                best, best_confirmed = (t, hold), confirmed
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".cache/smd"))
    parser.add_argument("--out", type=Path, default=Path("results/mahagauri"))
    parser.add_argument("--revision", default=smd_run.REVISION)
    parser.add_argument("--machines", type=int, default=len(smd.MACHINES))
    args = parser.parse_args()

    started = time.time()
    eps: list[dict] = []
    for name in smd.MACHINES[: args.machines]:
        m = smd.machine(name, args.cache, args.revision)
        m["features"] = smd_run.aggregate(m["train"], m["test"])
        eps.extend(episodes(m))
    for ep in eps:
        ep["frame"], ep["y"] = frame(ep), labels(ep)
        ep["frame3"] = trajectory(ep["frame"])
    groups = sorted({ep["group"] for ep in eps})
    print(f"SMD: {len(eps)} incidents with an hour of clean history, across {len(groups)} machine groups")

    folds = []
    for held in groups:
        train = [ep for ep in eps if ep["group"] != held]
        test = [ep for ep in eps if ep["group"] == held]
        if not train or not test:
            continue
        booster = lgb.train(detect_model.PARAMS, lgb.Dataset(pd.concat([ep["frame"] for ep in train], ignore_index=True),
                                                              label=np.concatenate([ep["y"] for ep in train])),
                            num_boost_round=detect_model.ROUNDS)
        train_probs = [booster.predict(ep["frame"]) for ep in train]
        t = choose(train, train_probs)
        t_upper = choose(train, train_probs, upper=True)
        within = [ep["frame"]["pre_beyond_3"].to_numpy() == 0 for ep in train]
        t_agree = choose(train, train_probs, upper=True, agree=within)
        oof = out_of_fold(train)
        t2, hold2 = choose_v2(train, oof)
        t2a, hold2a = choose_v2(train, oof, agree=within)
        booster3, oof3 = fit(train, "frame3"), out_of_fold(train, "frame3")
        t3, hold3 = choose_v2(train, oof3)
        t3a, hold3a = choose_v2(train, oof3, agree=within)
        timer = int(np.median([ep["end"] - ep["start"] for ep in train]))
        fold = {
            "held_out": held, "incidents": len(test), "train_incidents": len(train),
            "threshold": t, "threshold_upper": t_upper, "threshold_agree": t_agree, "timer_minutes": timer,
            "v2": {"threshold": t2, "hold": hold2, "agree_threshold": t2a, "agree_hold": hold2a},
            "v3": {"threshold": t3, "hold": hold3, "agree_threshold": t3a, "agree_hold": hold3a},
            "verifiers": {
                "mahagauri-v0": summary([outcome(ep, booster.predict(ep["frame"]) >= t) for ep in test]),
                "mahagauri-v1 (upper-bound threshold)": summary(
                    [outcome(ep, booster.predict(ep["frame"]) >= t_upper) for ep in test]),
                "mahagauri-v1 + 3σ agreement": summary(
                    [outcome(ep, (booster.predict(ep["frame"]) >= t_agree) & (ep["frame"]["pre_beyond_3"].to_numpy() == 0))
                     for ep in test]),
                "mahagauri-v2 (out-of-fold, hold chosen)": summary(
                    [outcome(ep, booster.predict(ep["frame"]) >= t2, hold2) for ep in test]),
                "mahagauri-v2 + 3σ agreement": summary(
                    [outcome(ep, (booster.predict(ep["frame"]) >= t2a) & (ep["frame"]["pre_beyond_3"].to_numpy() == 0),
                             hold2a) for ep in test]),
                "mahagauri-v3 (trajectory features)": summary(
                    [outcome(ep, booster3.predict(ep["frame3"]) >= t3, hold3) for ep in test]),
                "mahagauri-v3 + 3σ agreement": summary(
                    [outcome(ep, (booster3.predict(ep["frame3"]) >= t3a) & (ep["frame"]["pre_beyond_3"].to_numpy() == 0),
                             hold3a) for ep in test]),
                "back within 3σ": summary([outcome(ep, ep["frame"]["pre_beyond_3"].to_numpy() == 0) for ep in test]),
                "fixed timer": summary([outcome(ep, np.arange(len(ep["y"])) >= timer) for ep in test]),
            },
        }
        folds.append(fold)
        print(f"  held out {held}: " + "  ".join(
            f"{k} premature {v['premature_rate']:.2f} delay {v['median_delay']}" for k, v in fold["verifiers"].items()))

    names = list(folds[0]["verifiers"]) if folds else []
    pooled = {}
    for n in names:
        weights = [f["incidents"] for f in folds]
        pooled[n] = {k: round(float(np.average([f["verifiers"][n][k] for f in folds], weights=weights)), 4)
                     for k in ("premature_rate", "confirmed_rate", "unconfirmed_rate")}
    results = {
        "model": "sati-mahagauri-v0",
        "dataset": {"name": "SMD (Server Machine Dataset)", "repo": smd.REPO, "revision": args.revision,
                    "incidents": len(eps), "groups": groups},
        "protocol": {"horizon_minutes": HORIZON, "baseline_minutes": BASELINE, "consecutive": CONSECUTIVE,
                     "premature_budget": PREMATURE_BUDGET},
        "folds": folds,
        "pooled": pooled,
        "seconds": round(time.time() - started, 1),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
