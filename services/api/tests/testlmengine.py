"""The API's copy of Kushmanda's numpy engine is the one tested against PyTorch."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _engine(text: str) -> str:
    return text[text.index("import json") : text.index("def export(") if "def export(" in text else len(text)].strip()


def test_the_served_engine_is_the_tested_one():
    original = (ROOT / "packages" / "sati" / "sati" / "lm" / "infer.py").read_text(encoding="utf-8")
    served = (ROOT / "services" / "api" / "app" / "engines" / "lmengine.py").read_text(encoding="utf-8")
    assert _engine(served) == _engine(original), "lmengine.py drifted from sati.lm.infer; copy it again"
