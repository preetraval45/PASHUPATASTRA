"""The website reads the same results files the paper does.

Training workflows copy each results file to docs/research/models/ and to
apps/web/lib/models/. Results collected by hand from Kaggle are copied by hand,
and a copy that is missed or stale would put a number on the site that the
paper does not hold. This fails the build if any file present in both places
differs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "research" / "models"
WEB = ROOT / "apps" / "web" / "lib" / "models"
BOTH = sorted(p.name for p in WEB.glob("*.results.json") if (DOCS / p.name).exists())


@pytest.mark.parametrize("name", BOTH)
def test_web_copy_matches_the_paper_copy(name: str):
    assert (WEB / name).read_bytes().replace(b"\r\n", b"\n") == (DOCS / name).read_bytes().replace(b"\r\n", b"\n"), (
        f"apps/web/lib/models/{name} differs from docs/research/models/{name}")
