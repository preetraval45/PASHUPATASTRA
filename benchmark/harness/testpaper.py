"""RP-11's rule, enforced: every number in the paper's §7.1 is in tables.md.

A number typed into prose stops tracking the data the moment either changes,
and the stale number still looks like a number (PAPER.md, header). This fails
the build when §7.1 cites a rate, a p-value or a paired count that the
generated tables do not contain.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NUMBER = re.compile(r"\b\d+\.\d{3,4}\b|\b\d+ / \d+\b|\b\d+ of 93\b")


def _section() -> str:
    paper = (ROOT / "docs" / "research" / "PAPER.md").read_text(encoding="utf-8")
    start = paper.index("### 7.1 Baselines")
    body = paper[start : paper.index("\n## ", start)]
    return body[body.index("**Arms.**") :]  # after the editorial note, which names run ids and dates


def test_every_number_in_section_7_1_is_in_the_generated_tables():
    tables = (ROOT / "docs" / "research" / "tables.md").read_text(encoding="utf-8")
    cells = set(re.findall(r"\| *([^|]+?) *(?=\|)", tables))
    cited = set(NUMBER.findall(_section()))
    assert cited, "§7.1 should cite numbers from the tables"
    missing = []
    for n in sorted(cited):
        if n.endswith("of 93"):
            count = n.split()[0]
            if not any(cell == count for cell in cells):
                missing.append(n)
        elif n not in tables:
            missing.append(n)
    assert not missing, f"§7.1 cites numbers that tables.md does not contain: {missing}"
