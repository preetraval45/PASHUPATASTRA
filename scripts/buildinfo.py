"""Generate the stack list on the build panel from the manifests that define it.

R57's rule, and the reason this is a script rather than a hand-written array:
**a stack list claiming a dependency the repo does not have is the same failure
as an invented metric**, on the one panel whose entire subject is honesty. A
list typed from memory is correct on the day it is typed and slowly stops being
correct afterwards, silently, because nothing checks it.

So the names below are a *curation* — which dependencies are worth naming — and
every one of them is looked up in a real manifest. A name with no manifest entry
is an error that stops this script, not a line that renders anyway. Drop
`httpx` from `pyproject.toml` and the panel does not quietly keep advertising
it; the drift test in `testbuildinfo.py` fails.

Versions come from the manifests verbatim — `>=0.111`, not `0.111.x` — because
a range printed as a pin is a small lie of exactly the kind this panel exists
to avoid.

Run after changing a dependency:

    python scripts/buildinfo.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps" / "web" / "lib" / "buildinfo.generated.json"

WEB = "apps/web/package.json"
API = "services/api/pyproject.toml"
CORE = "packages/core/pyproject.toml"
CONNECTORS = "packages/connectors/pyproject.toml"

# (display name, package name, manifest). The display name is for a reader; the
# package name is what must exist in the manifest. Both are emitted so the test
# can check the second without trusting the first.
CURATED: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "Web",
        [
            ("Next.js", "next", WEB),
            ("React", "react", WEB),
            ("TypeScript", "typescript", WEB),
            ("Tailwind", "tailwindcss", WEB),
        ],
    ),
    (
        "API",
        [
            ("FastAPI", "fastapi", API),
            ("Pydantic", "pydantic", CORE),
            ("Uvicorn", "uvicorn", API),
            # The ASGI-to-Lambda adapter. Named because "runs on Lambda" is a
            # claim about the deployment and this is the thing that makes it true.
            ("Mangum", "mangum", API),
        ],
    ),
    (
        "Data and cloud",
        [
            ("boto3", "boto3", API),
            ("psycopg", "psycopg", API),
            ("httpx", "httpx", CONNECTORS),
        ],
    ),
    (
        "Checked with",
        [
            ("pytest", "pytest", API),
            ("ruff", "ruff", API),
            ("mypy", "mypy", API),
        ],
    ),
]


def _npm(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for section in ("dependencies", "devDependencies"):
        found.update(data.get(section) or {})
    return found


def _python(path: Path) -> dict[str, str]:
    """Every dependency in the file, optional extras included.

    Extras count: `boto3` and `mangum` live under `[project.optional-dependencies]`
    because only the AWS deployment installs them, and the panel is describing
    exactly that deployment.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project") or {}
    specs: list[str] = list(project.get("dependencies") or [])
    for extra in (project.get("optional-dependencies") or {}).values():
        specs.extend(extra)

    found: dict[str, str] = {}
    for spec in specs:
        # "psycopg[binary]>=3.2" -> ("psycopg", ">=3.2")
        match = re.match(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?\s*(.*)$", spec.strip())
        if match:
            found[match.group(1).lower()] = match.group(2).strip() or "*"
    return found


def manifests() -> dict[str, dict[str, str]]:
    return {
        WEB: _npm(ROOT / WEB),
        API: _python(ROOT / API),
        CORE: _python(ROOT / CORE),
        CONNECTORS: _python(ROOT / CONNECTORS),
    }


def build() -> dict:
    found = manifests()
    missing: list[str] = []
    groups = []

    for role, entries in CURATED:
        items = []
        for display, package, manifest in entries:
            version = found[manifest].get(package.lower())
            if version is None:
                missing.append(f"{package} (named for {role}, not in {manifest})")
                continue
            items.append(
                {
                    "name": display,
                    "package": package,
                    "version": version,
                    "manifest": manifest,
                }
            )
        groups.append({"role": role, "items": items})

    if missing:
        raise SystemExit(
            "buildinfo names dependencies that no manifest carries:\n  "
            + "\n  ".join(missing)
            + "\n\nEither the dependency was removed and the panel must stop "
            "claiming it, or the manifest is wrong. Do not delete the check."
        )

    return {
        "note": (
            "Generated by scripts/buildinfo.py from the repository's own "
            "manifests. Do not edit by hand."
        ),
        "manifests": [WEB, API, CORE, CONNECTORS],
        "groups": groups,
    }


def commit() -> str | None:
    """The short sha, recorded at generation time as a fallback only.

    On Vercel the panel prefers `VERCEL_GIT_COMMIT_SHA`, which is the commit
    actually deployed. This value is whatever was checked out when the file was
    generated, and it goes stale the moment anything else is committed — which
    is why it is a fallback for local runs and never the headline.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


if __name__ == "__main__":
    payload = build()
    payload["generated_at_commit"] = commit()
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    named = sum(len(group["items"]) for group in payload["groups"])
    print(f"{OUT.relative_to(ROOT)}: {named} dependencies, all found in manifests")
    sys.exit(0)
