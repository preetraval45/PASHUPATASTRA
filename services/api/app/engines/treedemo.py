"""Run an exported tree model live on its own held-out examples.

For models whose input is a feature vector rather than a question: Kalaratri
(log sessions) and Chandraghanta (network flows). Each export ships the
booster (`pashupatastra.trees`), its threshold, and a few test examples it
never trained on with their truth. The score is computed per request, and the
truth is returned beside it. Both are trained on research-use-only data and
are served on that basis (owner decision); the licence travels with each answer.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pashupatastra import trees

FOLDER = Path(__file__).resolve().parents[1] / "sati_models"
FORMS = ("kalaratri", "chandraghanta")


def available(form: str) -> bool:
    return form in FORMS and (FOLDER / f"{form}.json").exists()


@lru_cache
def served(form: str) -> dict:
    return json.loads((FOLDER / f"{form}.json").read_text(encoding="utf-8"))


def summary(form: str) -> dict:
    m = served(form)
    return {
        "model": form, "dataset": m.get("dataset") or m.get("split"), "licence": m.get("licence"),
        "operating_point": m.get("operating_point"),
        "examples": [{"id": e["id"], "label": e["label"]} for e in m.get("examples", [])],
    }


def run(form: str, example_id: str) -> dict:
    m = served(form)
    e = next((x for x in m.get("examples", []) if x["id"] == example_id), None)
    if e is None:
        raise KeyError(example_id)
    score = trees.predict(m, trees.row_from(m, e["features"]))
    flagged = score >= m["threshold"]
    return {
        "model": form, "example": e["id"], "label": e["label"], "score": round(score, 4),
        "threshold": round(float(m["threshold"]), 4), "flagged": flagged, "truth": bool(e["truth"]),
        "correct": flagged == bool(e["truth"]), "licence": m.get("licence"),
    }
