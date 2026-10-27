"""Shailaputri, Siddhidatri and Mahagauri, served: run on a server incident they never saw.

The models and incidents come from `sati.detect.serve`: trained on two SMD
machine groups, with the incidents taken from the third. Everything below is
computed per request with `pashupatastra.trees` and plain arithmetic; the
export checked that the tree scores equal LightGBM's. The labelled truth comes
back beside every answer.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from pashupatastra import trees

MODEL = Path(__file__).resolve().parents[1] / "sati_models" / "smd.json"


def available() -> bool:
    return MODEL.exists()


@lru_cache
def served() -> dict:
    return json.loads(MODEL.read_text(encoding="utf-8"))


def summary() -> dict:
    s = served()
    return {
        "held_out_group": s["held_out_group"],
        "trained_on": s["trained_on"],
        "incidents": [{"id": d["id"], "machine": d["machine"], "minutes": d["minutes"],
                       "length": d["incident"][1] - d["incident"][0]} for d in s["incidents"]],
    }


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


def run(incident_id: str) -> dict:
    s = served()
    d = next((x for x in s["incidents"] if x["id"] == incident_id), None)
    if d is None:
        raise KeyError(incident_id)
    m = s["models"]
    start, end = d["incident"]

    shail = [trees.predict(m["shailaputri"], r) for r in d["features"]]
    flags = [p >= m["shailaputri"]["threshold"] for p in shail]

    w = m["siddhidatri"]["weights"]
    fused = []
    for r, (z, pca) in zip(d["features"], d["statistical"], strict=True):
        x = [trees.predict(m["siddhidatri_input"], r), z or 0.0, pca or 0.0]
        fused.append(_sigmoid(sum(a * b for a, b in zip(w[:-1], x, strict=True)) + w[-1]))

    # Mahagauri answers from the incident's onset: recovered when its score
    # clears the threshold and no metric is beyond 3σ, for `hold` minutes running.
    maha = m["mahagauri"]
    agree = maha["features"].index("pre_beyond_3")
    run_len, declared = 0, None
    for i, r in enumerate(d["verify"]):
        ok = trees.predict(maha, r) >= maha["threshold"] and (r[agree] or 0.0) == 0.0
        run_len = run_len + 1 if ok else 0
        if run_len >= maha["hold"]:
            declared = start + i
            break

    flagged_inside = any(flags[start:end])
    first_flag = next((i for i in range(start, end) if flags[i]), None)
    return {
        "id": d["id"], "machine": d["machine"], "minutes": d["minutes"], "incident": [start, end],
        "truth": d["truth"],
        "shailaputri": {"score": [round(p, 4) for p in shail], "flags": flags,
                        "caught": flagged_inside, "first_flag": first_flag,
                        "false_flags_before": sum(flags[:start])},
        "siddhidatri": {"probability": [round(p, 4) for p in fused],
                        "flags": [p >= m["siddhidatri"]["threshold"] for p in fused]},
        "mahagauri": {"declared_over": declared,
                      "verdict": "unconfirmed" if declared is None else "premature" if declared < end else "confirmed"},
    }
