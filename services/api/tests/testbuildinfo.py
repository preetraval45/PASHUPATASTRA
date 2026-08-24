"""The build panel's stack list, checked against the manifests it claims to read.

R57's done-when is "every framework named is in a manifest in this repo", and
the failure it guards against is quiet: a dependency is dropped, the panel keeps
advertising it, and the one panel whose subject is that this site's claims can
be checked is the panel making an unchecked claim.

So these tests re-parse the manifests themselves rather than asking the
generator what it found. A test that calls `build()` and compares it to
`build()` proves the function is deterministic and nothing else.

Paths resolve from `__file__`, not from the working directory. `testpib.py` in
`packages/core` resolves its corpus relative to the cwd and silently loads zero
scenarios when pytest is run from anywhere but the repository root — a test that
measures nothing while reporting green is the failure mode this whole file
exists to prevent.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GENERATED = ROOT / "apps" / "web" / "lib" / "buildinfo.generated.json"
STACK = ROOT / "apps" / "web" / "components" / "builtwith.tsx"
ATTRIBUTION = ROOT / "apps" / "web" / "components" / "attribution.tsx"


def _generator():
    """Load `scripts/buildinfo.py` by path — it is a script, not an installed
    module, and the API package must not grow a dependency on the repo layout
    beyond this one test."""
    spec = importlib.util.spec_from_file_location(
        "pashupatastra_buildinfo", ROOT / "scripts" / "buildinfo.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _committed() -> dict:
    return json.loads(GENERATED.read_text(encoding="utf-8"))


def _declared(manifest: str) -> dict[str, str]:
    """Every dependency in one manifest, parsed here rather than by the code
    under test."""
    path = ROOT / manifest
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        found: dict[str, str] = {}
        for section in ("dependencies", "devDependencies"):
            found.update(data.get(section) or {})
        return found

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project") or {}
    specs = list(project.get("dependencies") or [])
    for extra in (project.get("optional-dependencies") or {}).values():
        specs.extend(extra)

    found = {}
    for spec in specs:
        match = re.match(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?\s*(.*)$", spec.strip())
        if match:
            found[match.group(1).lower()] = match.group(2).strip() or "*"
    return found


def named() -> list[dict]:
    return [item for group in _committed()["groups"] for item in group["items"]]


# --- the done-when ----------------------------------------------------------------


def test_every_named_dependency_is_in_the_manifest_it_cites() -> None:
    """The whole point. A name on the panel with no manifest entry behind it is
    an invented metric wearing a version number."""
    for item in named():
        declared = _declared(item["manifest"])
        assert item["package"].lower() in declared, (
            f"the panel names {item['package']} and cites {item['manifest']}, "
            f"which does not declare it"
        )


def test_the_version_shown_is_the_version_declared() -> None:
    """Ranges stay ranges. `>=0.111` rendered as `0.111` reads as a pin, which
    is a smaller lie than an invented dependency and the same kind."""
    for item in named():
        assert item["version"] == _declared(item["manifest"])[item["package"].lower()]


def test_the_committed_file_has_not_drifted_from_the_manifests() -> None:
    """Regenerating must be a no-op. If it is not, someone changed a dependency
    and the panel is still describing the old one."""
    fresh = _generator().build()
    assert fresh["groups"] == _committed()["groups"], (
        "run: python scripts/buildinfo.py"
    )
    assert fresh["manifests"] == _committed()["manifests"]


def test_the_generator_rejects_a_name_no_manifest_carries() -> None:
    """The check above only means something if the generator would actually
    fail. Asserted by feeding it a dependency that does not exist rather than by
    reading the code and believing it."""
    module = _generator()
    module.CURATED = [("Web", [("Nonesuch", "definitely-not-installed", module.WEB)])]
    with pytest.raises(SystemExit) as raised:
        module.build()
    assert "definitely-not-installed" in str(raised.value)


def test_the_generator_finds_dependencies_declared_as_extras() -> None:
    """`boto3` and `mangum` are under `[project.optional-dependencies]` because
    only the AWS deployment installs them — and the panel is describing exactly
    that deployment. A parser that read only `dependencies` would drop both and
    the panel would stop naming the thing it runs on."""
    packages = {item["package"] for item in named()}
    assert {"boto3", "mangum"} <= packages


# --- what kind of panel it is -------------------------------------------------------


def test_the_stack_list_is_not_typed_into_the_component() -> None:
    """It has to come from the generated file, or none of the above applies."""
    source = STACK.read_text(encoding="utf-8")
    assert "buildinfo.generated.json" in source
    for item in named():
        # The display name may appear in the JSON; it must not appear as a
        # literal in the component.
        assert f'"{item["name"]}"' not in source, (
            f"{item['name']} is hardcoded in the panel instead of read from the manifest"
        )


def test_attribution_reads_as_a_credit_not_a_bio() -> None:
    """R57 is explicit: no photograph, no first person, no "passionate about".
    The site's argument is that it states only what it can show, and a bio in a
    different register than every other line is where a reader stops believing
    that."""
    body = ATTRIBUTION.read_text(encoding="utf-8")
    # Only the rendered half — the file's own docstring discusses these words.
    rendered = body[body.index("export function Attribution") :].lower()
    for phrase in ("passionate", "i'm ", "i am ", " my ", "enthusiast", "<img"):
        assert phrase not in rendered, f"the attribution contains {phrase!r}"


def test_the_stack_is_not_on_every_page() -> None:
    """The first version of this put a bill of materials in the global layout —
    dependency versions and the manifest paths they came from, under every page
    on the site. That is the build describing its own working conditions to
    someone who came to read about an incident.

    Attribution is one line and belongs everywhere; the stack is a page someone
    opens on purpose."""
    layout = (ROOT / "apps" / "web" / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert "BuiltWith" not in layout
    assert "buildinfo.generated" not in layout
    assert "Attribution" in layout


def test_the_stack_shows_names_without_versions() -> None:
    """Versions were the noisiest half and say nothing a reader of that page
    wants. They stay in the generated file, where the drift tests use them."""
    source = STACK.read_text(encoding="utf-8")
    assert "item.version" not in source
    assert "item.name" in source
