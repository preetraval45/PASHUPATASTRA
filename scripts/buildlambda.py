"""Build the API deployment archive for AWS Lambda.

The demo deployment runs with no database, no Redis, and no OpenSearch: the
stores fall back to memory, health reports `degraded`, and the scenario corpus
is replayed into the graph so the dashboard has something true to render. See
`docs/DEPLOYMENT.md`.

Dependencies are resolved for the Lambda runtime's platform, not this machine's.
Building on Windows or macOS and shipping the wheels that produced would install
binaries the runtime cannot load, and the failure surfaces as an import error on
the first request rather than at build time.

`psycopg` is deliberately absent. `app/db.py` imports it inside `connect`, so a
deployment that never opens a database connection does not carry the driver —
which is a third of the archive.

Usage:  python scripts/buildlambda.py [--out dist/api.zip]
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_PYTHON = "3.13"
RUNTIME_PLATFORM = "manylinux2014_x86_64"

PYPROJECTS = [
    ROOT / "services" / "api" / "pyproject.toml",
    ROOT / "packages" / "core" / "pyproject.toml",
    ROOT / "packages" / "connectors" / "pyproject.toml",
]

EXTRA_DEPENDENCIES = ["mangum>=0.17"]
"""Needed by the Lambda entry point only, so it is an optional extra rather than
a runtime dependency of the API."""

OMIT = ("pashupatastra-", "psycopg")
"""`pashupatastra-*` travel as source, copied by `stage_sources`. `psycopg` is
imported lazily inside `db.connect`, so a deployment with no database does not
need it — and it is a third of the archive."""


def dependencies() -> list[str]:
    """Every runtime dependency the three packages declare.

    Read from the pyprojects rather than listed here. A hand-maintained copy
    drifts silently, and the failure lands at runtime on the first request as an
    import error, not at build time.
    """
    import tomllib

    found: dict[str, str] = {}
    for pyproject in PYPROJECTS:
        declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        for requirement in declared["project"]["dependencies"]:
            name = re.split(r"[<>=!\[ ]", requirement, maxsplit=1)[0]
            if not name.startswith(OMIT):
                found.setdefault(name, requirement)
    return sorted(found.values()) + EXTRA_DEPENDENCIES


SOURCES = [
    (ROOT / "services" / "api" / "app", "app"),
    (ROOT / "packages" / "core" / "pashupatastra", "pashupatastra"),
    (ROOT / "packages" / "connectors" / "drishti", "drishti"),
]

CORPUS = (ROOT / "benchmark" / "incidents", "benchmark/incidents")
"""Bundled because `app/seed.py` replays it at startup. Only the scenario files
travel — the harness under `benchmark/harness/` drives a Kubernetes cluster and
has no business in a Lambda archive."""

EXCLUDE = {"__pycache__", ".pytest_cache", ".mypy_cache"}


def stage_dependencies(stage: Path) -> None:
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--quiet", "--target", str(stage),
            "--platform", RUNTIME_PLATFORM,
            "--python-version", RUNTIME_PYTHON,
            "--implementation", "cp",
            "--only-binary=:all:",
            *dependencies(),
        ],
        check=True,
    )


def stage_sources(stage: Path) -> None:
    ignore = shutil.ignore_patterns(*EXCLUDE, "*.pyc")
    for source, target in SOURCES:
        shutil.copytree(source, stage / target, ignore=ignore, dirs_exist_ok=True)

    corpus_source, corpus_target = CORPUS
    destination = stage / corpus_target
    destination.mkdir(parents=True, exist_ok=True)
    for scenario in corpus_source.glob("*.yaml"):
        shutil.copy2(scenario, destination / scenario.name)


def archive(stage: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(stage.rglob("*")):
            if path.is_file() and not any(part in EXCLUDE for part in path.parts):
                bundle.write(path, path.relative_to(stage).as_posix())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "dist" / "api.zip"))
    parser.add_argument(
        "--stage",
        default=None,
        help="where to assemble the bundle. Defaults to a temporary directory "
             "outside the working copy: staging inside a synced folder leaves "
             "the sync client holding open handles on __pycache__, and the "
             "next build fails trying to clear it.",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="pashupatastra-lambda-") as temporary:
        stage = Path(args.stage) if args.stage else Path(temporary)
        if args.stage and stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True, exist_ok=True)

        stage_dependencies(stage)
        stage_sources(stage)
        out = archive(stage, Path(args.out))

    print(f"{out}  {out.stat().st_size / 1_048_576:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
