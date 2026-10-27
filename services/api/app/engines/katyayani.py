"""Katyayani, served: rank the services of an incident it never trained on.

The model and the incidents come from `sati.rca.serve`, which trains on real
fault injections and reserves one incident in ten for this. The ranking is
computed here, on each request, by `pashupatastra.trees` (plain Python, no
LightGBM), and the export checked that this gives LightGBM's scores. The true
root cause is returned beside the ranking, so a visitor sees when it is wrong.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pashupatastra import trees

MODEL = Path(__file__).resolve().parents[1] / "sati_models" / "katyayani.json"


def available() -> bool:
    return MODEL.exists()


@lru_cache
def served() -> dict:
    return json.loads(MODEL.read_text(encoding="utf-8"))


def summary() -> dict:
    m = served()
    return {
        "trained_on": m["trained_on"],
        "reserved": m["reserved"],
        "cases": [{"id": c["id"], "system": c["system"], "services": len(c["services"])} for c in m["cases"]],
    }


def rank(case_id: str) -> dict:
    m = served()
    case = next((c for c in m["cases"] if c["id"] == case_id), None)
    if case is None:
        raise KeyError(case_id)
    booster = m["booster"]
    scored = sorted(
        ({"service": s["name"], "score": round(trees.predict(booster, trees.row_from(booster, s["features"])), 4),
          "evidence": s["shown"]} for s in case["services"]),
        key=lambda r: -r["score"],
    )
    return {
        "case": case["id"],
        "system": case["system"],
        "ranking": scored,
        "root": case["root"],
        "correct": scored[0]["service"] == case["root"],
        "position": next(i for i, r in enumerate(scored, start=1) if r["service"] == case["root"]),
        "reserved": m["reserved"],
    }
