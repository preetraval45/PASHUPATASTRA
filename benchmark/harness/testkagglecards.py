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


#: A model's own tables. A number found only in another model's table is a stale number that happens
#: to match, which is how 0.534 and 0.530 survived in Siddhidatri's description.
OWN = {"katyayani": ("sati-rca", "katyayani", "rcaeval-diagnosis")}


@pytest.mark.parametrize("name", sorted(kagglemodels.MODELS))
def test_kaggle_description_numbers_are_in_a_generated_table(name: str):
    prefixes = OWN.get(name, (name,))
    tables = "\n".join(p.read_text(encoding="utf-8") for p in MODELS.glob("*.md") if p.name.startswith(prefixes))
    cited = set(NUMBER.findall(kagglemodels.MODELS[name]["description"]))
    missing = [n for n in sorted(cited) if n not in tables and f"{float(n) / 100:.3f}" not in tables]
    assert not missing, f"the {name} Kaggle description cites numbers no generated table contains: {missing}"


notebooks_spec = importlib.util.spec_from_file_location("kagglenotebooks", ROOT / "scripts" / "kagglenotebooks.py")
kagglenotebooks = importlib.util.module_from_spec(notebooks_spec)
notebooks_spec.loader.exec_module(kagglenotebooks)  # type: ignore[union-attr]
EXACT = re.compile(r"(?<![\w.\-])\d+\.\d{3}(?![\w.])")  # a figure quoted to three places is a claim, not an "about"


@pytest.mark.parametrize("name", sorted(kagglenotebooks.NOTEBOOKS))
def test_kaggle_notebook_prose_cites_only_numbers_in_its_models_tables(name: str):
    prefixes = OWN.get(name, (name,))
    tables = "\n".join(p.read_text(encoding="utf-8") for p in MODELS.glob("*.md") if p.name.startswith(prefixes))
    prose = " ".join(text for kind, text in kagglenotebooks.NOTEBOOKS[name]["cells"] if kind == "markdown")
    prose = re.sub(r"\babout \d+\.\d+", "", prose)  # the notebook's own run, stated as approximate
    missing = [n for n in sorted(set(EXACT.findall(prose))) if n not in tables]
    assert not missing, f"the {name} notebook's text cites numbers its model's tables do not hold: {missing}"
