"""R108: the citation on the site is `CITATION.cff`, rendered — nothing else.

The same discipline as `testbuildinfo.py`: the committed JSON the page renders
is regenerated here from the file GitHub reads and compared, so a change to
one that forgot the other fails the build rather than shipping two citations.
The DOI clause is the one worth having: a DOI that is not in the file must not
appear on the page, and the page must say so rather than leave a gap.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CFF = ROOT / "CITATION.cff"
GENERATED = ROOT / "apps" / "web" / "lib" / "citation.generated.json"


def _generator():
    spec = importlib.util.spec_from_file_location(
        "pashupatastra_buildcitation", ROOT / "scripts" / "buildcitation.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_committed_citation_is_the_cff_file_rendered() -> None:
    cff = yaml.safe_load(CFF.read_text(encoding="utf-8"))
    fresh = _generator().render(cff)
    committed = json.loads(GENERATED.read_text(encoding="utf-8"))
    assert committed == fresh, "run python scripts/buildcitation.py"


def test_the_cff_file_is_valid_and_names_the_author() -> None:
    cff = yaml.safe_load(CFF.read_text(encoding="utf-8"))
    assert cff["cff-version"] == "1.2.0"
    assert cff["authors"][0]["family-names"] == "Raval"
    assert cff["url"].startswith("https://")
    assert cff["repository-code"].startswith("https://github.com/")


def test_the_version_is_the_package_version_not_an_invented_one() -> None:
    """There are no releases yet, so the only version that can be cited is the
    one the package declares. A number typed to look like a release is the
    invented figure this repository refuses everywhere else."""
    import tomllib

    core = tomllib.loads((ROOT / "packages" / "core" / "pyproject.toml").read_text(encoding="utf-8"))
    cff = yaml.safe_load(CFF.read_text(encoding="utf-8"))
    assert str(cff["version"]) == core["project"]["version"]


def test_no_doi_is_shown_unless_the_file_carries_one() -> None:
    committed = json.loads(GENERATED.read_text(encoding="utf-8"))
    cff = yaml.safe_load(CFF.read_text(encoding="utf-8"))
    if "doi" not in cff:
        assert committed["doi"] is None
        assert "doi" not in committed["bibtex"]
        assert "doi.org" not in committed["apa"]
    else:
        assert committed["doi"] == cff["doi"]
        assert f"doi = {{{cff['doi']}}}" in committed["bibtex"]


def test_a_doi_in_the_file_reaches_both_renderings() -> None:
    cff = yaml.safe_load(CFF.read_text(encoding="utf-8"))
    rendered = _generator().render({**cff, "doi": "10.5281/zenodo.0000000"})
    assert "doi = {10.5281/zenodo.0000000}" in rendered["bibtex"]
    assert rendered["apa"].endswith("https://doi.org/10.5281/zenodo.0000000")
