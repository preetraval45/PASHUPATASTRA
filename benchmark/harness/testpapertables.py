"""Table 5's verdict is taken on the Holm-adjusted p, across the whole table."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "papertables", Path(__file__).resolve().parents[2] / "scripts" / "papertables.py"
)
papertables = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(papertables)


def _row(name: str, p: float | None) -> dict:
    return {"name": name, "p": p, "counts": "1 / 0", "ci": "[+0.000, +0.000]"}


def test_a_row_that_passes_alone_can_fail_across_the_family():
    rows = papertables.table5_rows([_row("a", 0.03), _row("b", 0.04), _row("c", 0.0001)])
    assert rows[0].endswith("within chance |")  # 0.03 alone would pass; adjusted it is 0.06
    assert rows[2].endswith("survives |")


def test_a_comparison_without_pairs_is_said_so_and_not_tested():
    rows = papertables.table5_rows([_row("a", None), _row("b", 0.001)])
    assert "no paired runs" in rows[0] and rows[1].endswith("survives |")
