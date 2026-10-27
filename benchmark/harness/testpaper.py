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
    end = min(i for i in (paper.find("\n## ", start), paper.find("\n### ", start + 1)) if i != -1)
    body = paper[start:end]
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


def test_every_number_in_section_7_2_is_in_a_generated_model_table():
    paper = (ROOT / "docs" / "research" / "PAPER.md").read_text(encoding="utf-8")
    start = paper.index("### 7.2 ")
    body = paper[start : paper.index("\n## ", start)]
    body = body[body.index("Nine models") :]  # after the editorial note
    models = ROOT / "docs" / "research" / "models"
    every = "\n".join(p.read_text(encoding="utf-8") for p in models.glob("*.md"))
    missing = []
    # Checked per paragraph or bullet: one that links a model table must find
    # its numbers in *that* table. Against all tables at once, a stale number
    # passed whenever it happened to appear in some other model's table.
    for block in re.split(r"\n\s*\n|\n(?=- )", body):
        linked = [models / f for f in re.findall(r"\(models/([\w.-]+\.md)\)", block)]
        tables = "\n".join(p.read_text(encoding="utf-8") for p in linked if p.exists()) or every
        for n in sorted(set(re.findall(r"\b\d+\.\d{1,4}\b", block))):
            # A percentage in prose may appear as a share in a table (88.4% ↔ 88.4 or 0.884).
            variants = {n, f"{float(n) / 100:.3f}"} if float(n) > 1 else {n}
            if not any(v in tables for v in variants):
                missing.append(n)
    assert not missing, f"§7.2 cites numbers no model table contains: {missing}"


def test_every_number_in_section_8_is_in_the_table_it_links():
    """§8 is drafted from generated tables too; the same per-paragraph rule."""
    paper = (ROOT / "docs" / "research" / "PAPER.md").read_text(encoding="utf-8")
    start = paper.index("## 8. Failure analysis")
    body = paper[start : paper.index("\n## 9", start)]
    research = ROOT / "docs" / "research"
    missing = []
    for block in re.split(r"\n\s*\n|\n(?=- )", body):
        linked = [research / f for f in re.findall(r"\(((?:models|review)/[\w.-]+\.md)\)", block)]
        tables = "\n".join(p.read_text(encoding="utf-8") for p in linked if p.exists())
        if not tables:
            continue  # a paragraph with no table link cites no table numbers
        for n in sorted(set(re.findall(r"\b\d+\.\d{1,4}\b", block))):
            if n not in tables:
                missing.append(n)
    assert not missing, f"§8 cites numbers its linked tables do not contain: {missing}"
