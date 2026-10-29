"""The public Kaggle model descriptions cite only numbers the generated tables hold.

`scripts/kagglemodels.py` writes each model's description by hand, and a
retrain moves the tables under docs/research/models/. On 29 Oct two published
descriptions still quoted numbers from an earlier run. This fails the build
when a description cites a number no generated table contains, as
testcards.py does for the model cards.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "docs" / "research" / "models"
NUMBER = re.compile(r"(?<![\w.\-])\d+\.\d{1,4}(?![\w.])")

spec = importlib.util.spec_from_file_location("kagglemodels", ROOT / "scripts" / "kagglemodels.py")
kagglemodels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kagglemodels)  # type: ignore[union-attr]


@pytest.mark.parametrize("name", sorted(kagglemodels.MODELS))
def test_kaggle_description_numbers_are_in_a_generated_table(name: str):
    tables = "\n".join(p.read_text(encoding="utf-8") for p in MODELS.glob("*.md"))
    cited = set(NUMBER.findall(kagglemodels.MODELS[name]["description"]))
    missing = [n for n in sorted(cited) if n not in tables and f"{float(n) / 100:.3f}" not in tables]
    assert not missing, f"the {name} Kaggle description cites numbers no generated table contains: {missing}"
