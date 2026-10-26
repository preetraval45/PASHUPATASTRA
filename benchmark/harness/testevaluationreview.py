"""The /evaluation page's review statuses change only when the run records justify it."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "buildevaluation", Path(__file__).resolve().parents[2] / "scripts" / "buildevaluation.py"
)
buildevaluation = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(buildevaluation)


def _status(recorded: dict, key: str) -> str:
    return next(f["status"] for f in buildevaluation.review(recorded) if f["key"] == key)


def _arm(records: int, repeats: int, models: list[str] | None = None) -> dict:
    return {"records": records, "scenarios": 31, "repeats": repeats, "ablations": [], "models": models or []}


def test_with_no_records_every_status_is_as_reviewed():
    assert [f["status"] for f in buildevaluation.review({})] == [f["status"] for f in buildevaluation.REVIEW]


def test_thin_is_answered_only_when_every_arm_repeats_three_times():
    assert _status({"runbook": _arm(93, 3), "pashupatastra": _arm(31, 1)}, "thin") == "open"
    answered = _status({"runbook": _arm(93, 3), "pashupatastra": _arm(93, 3)}, "thin")
    assert answered.startswith("answered by the records") and "186 runs" in answered


def test_the_model_finding_names_the_models_and_keeps_diagnosis_open():
    status = _status({"naive-llm": _arm(279, 3, ["llama3", "mistral"]), "pashupatastra-llm": _arm(279, 3, ["llama3"])},
                     "model")
    assert "2 local models (llama3, mistral)" in status and "558 runs" in status
    assert "Diagnosis accuracy is still unmeasured" in status
