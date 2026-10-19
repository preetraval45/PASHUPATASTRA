# Reproducibility: one command, and a gap it found

- **Date:** 2026-10-18
- **Phase:** Block E — Paper (RP-39)
- **Commit(s):** pending

## What changed

`scripts/reproduce.py --check` rebuilds every generated table from the committed results files. Added `docs/research/REPRODUCIBILITY.md` and model cards for Kalaratri and Brahmacharini.

## Why

RP-39 asks for one command that rebuilds every table, run from a clean checkout. The four model tables rebuild byte-for-byte.

## Decisions made

- `benchmark.yml` now commits `benchmark/results/` (with `git add -f`, because the folder is gitignored) alongside `tables.md`. Before this, the records lived only in Actions artifacts, which expire after 90 days, so `tables.md` could not be rebuilt.
- Training is not part of `reproduce.py`. The workflows rerun training; the script rebuilds tables only.

## Next session should

- After the next benchmark run, confirm that `reproduce.py --check` reports `tables.md` as the same. Then consider making the check a CI job.
- Write the Kushmanda card once its results land.
