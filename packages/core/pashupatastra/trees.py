"""Gradient-boosted trees, evaluated in plain Python.

Five of Sati's nine models are LightGBM boosters (Katyayani, Shailaputri,
Kalaratri, Chandraghanta, Mahagauri). The API runs on a lean Lambda, and this
package must run anywhere with no dependencies, so a trained booster is
exported as JSON (`compact`) and evaluated here by walking its trees.

Missing values follow LightGBM's rules for numerical splits, which differ by
the split's `missing_type`:

* ``None``: a missing value is treated as 0.0 and compared.
* ``NaN``: a missing value goes the split's default direction.
* ``Zero``: a missing value *or* zero goes the default direction.

A parity test checks this against LightGBM itself (packages/sati/tests). An
exported model is data, not code: it holds thresholds and leaf values only.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

_MISSING = {"None": 0, "NaN": 1, "Zero": 2}


def _node(n: dict) -> object:
    if "leaf_value" in n:
        return float(n["leaf_value"])
    if n.get("decision_type", "<=") != "<=":
        raise ValueError("categorical splits are not supported; Sati's models use none")
    return [int(n["split_feature"]), float(n["threshold"]), bool(n["default_left"]),
            _MISSING[n.get("missing_type", "None")], _node(n["left_child"]), _node(n["right_child"])]


def compact(dump: dict, features: Sequence[str]) -> dict:
    """A LightGBM `Booster.dump_model()` → a compact, JSON-safe model."""
    return {
        "objective": str(dump.get("objective", "")).split()[0],
        "features": list(features),
        "trees": [_node(t["tree_structure"]) for t in dump["tree_info"]],
    }


def _missing(x: float | None) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def _leaf(node: object, row: Sequence[float | None]) -> float:
    while isinstance(node, list):
        feature, threshold, default_left, missing, left, right = node
        x = row[feature]
        if missing == 0:  # None: missing compares as zero
            go_left = (0.0 if _missing(x) else x) <= threshold
        elif _missing(x) or (missing == 2 and x == 0.0):
            go_left = default_left
        else:
            go_left = x <= threshold
        node = left if go_left else right
    return node  # type: ignore[return-value]


def raw_score(model: dict, row: Sequence[float | None]) -> float:
    return sum(_leaf(t, row) for t in model["trees"])


def predict(model: dict, row: Sequence[float | None]) -> float:
    """The model's output: a probability for a binary model, the raw score otherwise (a ranker)."""
    z = raw_score(model, row)
    return 1.0 / (1.0 + math.exp(-z)) if model["objective"] == "binary" else z


def row_from(model: dict, values: dict[str, float | None]) -> list[float | None]:
    """A feature dict → the row in the model's feature order; absent features are missing."""
    return [values.get(f) for f in model["features"]]


def explain(model: dict, row: Sequence[float | None], top: int = 3) -> list[tuple[str, float]]:
    """The features that moved this row's score most, by ablation.

    Each feature the row has (present and non-zero) is set to missing in turn,
    as LightGBM treats missing, and the change in raw score (log-odds for a
    binary model) is recorded: positive means the feature pushed the score up.
    No internal node values are needed, so it works on any exported model. It
    answers "what would the model say without this?", one feature at a time;
    features that only matter together can each look small.
    """
    base = raw_score(model, row)
    effects = []
    for i, x in enumerate(row):
        if _missing(x) or x == 0.0:
            continue
        ablated = list(row)
        ablated[i] = None
        effects.append((model["features"][i], base - raw_score(model, ablated)))
    effects.sort(key=lambda e: -abs(e[1]))
    return effects[:top]
