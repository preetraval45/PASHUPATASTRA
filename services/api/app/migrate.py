"""Migration runner.

Applies the migrations listed in `migrations/manifest.txt`, in order, once each.
Each file runs inside a transaction and is recorded with a checksum, so an
already-applied migration that later changes on disk is an error rather than a
silent divergence between environments.

Usage:  python -m app.migrate [--database-url URL]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import psycopg

from .config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migration (
    filename   TEXT PRIMARY KEY,
    checksum   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def planned() -> list[str]:
    manifest = (MIGRATIONS_DIR / "manifest.txt").read_text(encoding="utf-8")
    return [
        line.strip()
        for line in manifest.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def migrate(database_url: str) -> list[str]:
    """Apply pending migrations. Returns the filenames applied this run."""
    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(_LEDGER)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT filename, checksum FROM schema_migration")
            known = dict(cur.fetchall())

        for filename in planned():
            path = MIGRATIONS_DIR / filename
            if not path.exists():
                raise FileNotFoundError(f"manifest lists {filename}, which does not exist")
            checksum = _checksum(path)

            if filename in known:
                if known[filename] != checksum:
                    raise RuntimeError(
                        f"{filename} was already applied but its contents changed. "
                        "Applied migrations are immutable — add a new migration instead."
                    )
                continue

            with conn.cursor() as cur:
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migration (filename, checksum) VALUES (%s, %s)",
                    (filename, checksum),
                )
            conn.commit()
            applied.append(filename)

    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Pashupatastra database migrations")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    url = args.database_url or get_settings().database_url
    applied = migrate(url)
    if applied:
        for filename in applied:
            print(f"applied {filename}")
    else:
        print("no pending migrations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
