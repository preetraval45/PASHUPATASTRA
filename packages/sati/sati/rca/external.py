"""The external-benchmark adapter (RP-32): RCAEval cases in, model inputs out, the answer kept apart.

Two rules, each enforced by a test:

* **The adapter's output never contains the label.** `inputs()` returns
  per-service features computed from the case's metrics and the authored
  graph only. The root-cause service and the fault type come from `answer()`,
  which only the scorer calls.
* **The subset is declared before any run.** `benchmark/external/rcaeval/subset.json`
  pins RCAEval's revision and lists every case, with a SHA-256 over the list.
  `load_subset` refuses a file whose list no longer matches its hash, so the
  subset cannot be edited after the fact without that being visible.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from sati.rca import features as rfeat
from sati.sources import rcaeval

LABEL_FIELDS = ("root_cause_service", "fault", "fault_description")


def load_subset(path: Path) -> dict:
    subset = json.loads(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256("\n".join(subset["cases"]).encode()).hexdigest()
    if digest != subset["cases_sha256"]:
        raise ValueError(f"{path}: the case list no longer matches its declared hash")
    return subset


def inputs(case: pd.Series, cache: Path, rev: str) -> pd.DataFrame:
    """What a model may see: per-service features from the metrics and the graph."""
    from sati.rca.simtoreal import kaal_features  # avoid a cycle: simtoreal uses this module

    frame = rcaeval.metrics(str(case["case"]), cache, rev)
    table, _ = rfeat.incident_features(frame, int(case["inject_time"]))
    table["case"] = case["case"]
    return kaal_features(table, str(case["system"]))


def answer(case: pd.Series) -> str:
    """The root-cause service, for the scorer only."""
    return str(case["root_cause_service"])
