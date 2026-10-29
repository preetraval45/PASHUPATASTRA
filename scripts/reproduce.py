"""Regenerate every generated results table from the committed run records.

    python scripts/reproduce.py           # rewrite the tables in place
    python scripts/reproduce.py --check   # fail if any committed table differs

The tables in docs/research/ are never typed by hand. Each one is produced by a
script from a results file that a workflow committed. This runs every one of
those scripts, so a clean checkout can show that the published numbers are
exactly what the records say. Training itself is rerun by the workflows
(train-sati.yml, benchmark.yml), not here, because it needs the datasets and
more compute than a laptop should spend. See docs/research/REPRODUCIBILITY.md.

Standard library only. The report scripts import nothing heavier than `json`.
"""

from __future__ import annotations

import argparse
import difflib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "docs" / "research" / "models"
SATI = ROOT / "packages" / "sati"

# (generated table, command that prints it, working directory)
TABLES = [
    (ROOT / "docs/research/tables.md", [sys.executable, "scripts/papertables.py"], ROOT),
    *[
        (MODELS / f"{name}.md", [sys.executable, "-m", module, str(MODELS / f"{name}.results.json")], SATI)
        for name, module in (
            ("sati-rca", "sati.rca.report"),
            ("katyayani-kaal", "sati.rca.kaalreport"),
            ("katyayani-simtoreal", "sati.rca.simtoreport"),
            ("katyayani-live", "sati.rca.livereport"),
            ("katyayani-live-signal", "sati.rca.livesignal"),
            ("shailaputri", "sati.detect.report"),
            ("shailaputri-smd", "sati.detect.smdreport"),
            ("kalaratri", "sati.loganomaly.report"),
            ("kalaratri-bgl", "sati.loganomaly.report"),
            ("brahmacharini", "sati.embed.report"),
            ("brahmacharini-transformer", "sati.embed.report"),
            ("chandraghanta", "sati.netdetect.report"),
            ("mahagauri", "sati.verify.report"),
            ("skandamata", "sati.respond.report"),
            ("siddhidatri", "sati.fuse.report"),
            ("kushmanda", "sati.lm.report"),
            ("kushmanda-v3", "sati.lm.report"),
            ("kushmanda-constrained", "sati.lm.constrainedreport"),
        )
    ],
]


def render(command: list[str], cwd: Path) -> str:
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False,
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if done.returncode:
        raise SystemExit(f"{' '.join(command)} failed:\n{done.stderr}")
    return done.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="compare instead of writing")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    differs = 0
    for table, command, cwd in TABLES:
        if not (MODELS / f"{table.stem}.results.json").exists() and table.parent == MODELS:
            print(f"skip   {table.relative_to(ROOT).as_posix()} (no results committed yet)")
            continue
        fresh = render(command, cwd)
        committed = table.read_text(encoding="utf-8") if table.exists() else ""
        same = fresh.replace("\r\n", "\n").rstrip() == committed.replace("\r\n", "\n").rstrip()
        if args.check:
            print(f"{'same  ' if same else 'DIFFERS'} {table.relative_to(ROOT).as_posix()}")
            if not same:
                differs += 1
                sys.stdout.writelines(difflib.unified_diff(
                    committed.splitlines(keepends=True), fresh.splitlines(keepends=True),
                    "committed", "regenerated", n=1))
        elif not same:
            table.write_text(fresh, encoding="utf-8")
            print(f"wrote  {table.relative_to(ROOT).as_posix()}")
    return 1 if differs else 0


if __name__ == "__main__":
    raise SystemExit(main())
