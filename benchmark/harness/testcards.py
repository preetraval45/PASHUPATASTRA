"""Model cards cite only numbers the generated tables hold.

A card's metrics are copied by hand from a generated table, and a retrain
moves that table. On 27 Oct three cards still showed numbers from runs since
replaced, one of them from before the false-alarm scoring fix. This fails the
build when a card's metrics section cites a number no table under
docs/research/models/ contains, so a retrain that moves a number also flags
the card that quotes it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MODELS = Path(__file__).resolve().parents[2] / "docs" / "research" / "models"
NUMBER = re.compile(r"(?<![\w.])\d+\.\d{1,4}(?![\w.])")
START = re.compile(r"\n## (Metrics|What the numbers say)")
END = re.compile(r"\n## (Known limitations|Ethical considerations|Intended use|Data)\b")


def _metrics(card: str) -> str:
    """From the first metrics heading to the next section that is not about results."""
    m = START.search(card)
    if not m:
        return ""
    body = card[m.start():]
    end = END.search(body, 1)
    return body[: end.start()] if end else body


CARDS = sorted((MODELS / "cards").glob("*.md"))


#: A card's own tables (by file-name prefix). A number found only in another model's table is a stale
#: number that happens to match; on 29 Oct that hid stale figures in Siddhidatri's Kaggle description.
OWN = {"katyayani": ("sati-rca", "katyayani", "rcaeval-diagnosis"), "shailaputri-smd": ("shailaputri",)}


@pytest.mark.parametrize("card", CARDS, ids=[c.stem for c in CARDS])
def test_card_numbers_are_in_a_generated_table(card: Path):
    prefixes = OWN.get(card.stem, (card.stem,))
    tables = "\n".join(p.read_text(encoding="utf-8") for p in MODELS.glob("*.md") if p.name.startswith(prefixes))
    cited = set(NUMBER.findall(_metrics(card.read_text(encoding="utf-8"))))
    # A percentage in prose may be a share in a table (54.3% ↔ 0.543).
    missing = [n for n in sorted(cited) if n not in tables and f"{float(n) / 100:.3f}" not in tables]
    assert not missing, f"{card.name} cites numbers no generated table contains: {missing}"
