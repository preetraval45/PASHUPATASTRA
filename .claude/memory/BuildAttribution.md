# Build attribution (R57)

## Why the first version was wrong

R57 asks for "a footer panel, styled as a system readout — version, deploy
target, stack". Built exactly that: revision, deploy target, every dependency
with its version range, and the manifest paths they were read from, on every
page. The owner rejected it immediately — *"it looks like it is showing the
stuff I am doing while building the website"* — and was right.

A bill of materials under every page is the build describing its own working
conditions to someone who came to read about an incident. `pytest · ruff · mypy`
with version ranges is of interest to exactly one person, who already knows.

**The lesson is not "make it smaller".** The task had conflated two things with
different audiences and different natural homes:

- **Attribution** — who built this, where the source is. One line. Belongs
  everywhere, because a site with no author is the omission that costs a
  portfolio project everything.
- **The stack** — what it is made of. A page someone opens on purpose.
  `/how-it-works`. Names only.

Splitting them fixed it. Shrinking the panel would not have.

## What survived, and why it was the part worth keeping

The honesty constraint. `scripts/buildinfo.py` reads `apps/web/package.json` and
the three `pyproject.toml` files, and **exits non-zero if asked to name a
dependency no manifest carries**. A stack list claiming a dependency the repo
does not have is the same failure as an invented metric.

`services/api/tests/testbuildinfo.py` re-parses the manifests itself rather than
asking the generator what it found — a test that calls `build()` and compares it
to `build()` proves determinism and nothing else. All four failure modes were
watched going red before being trusted green: stale version, invented
dependency, name typed into the component, bio phrase in the attribution.

Both `boto3` and `mangum` live under `[project.optional-dependencies]`, so the
parser reads extras too. A parser that read only `dependencies` would drop both
and the site would stop naming the thing it runs on.

## Two defects only the deployed check found

- The panel linked its commit sha to GitHub while the branch was unpushed — the
  one panel about verifiability shipped a **404**. The sha now renders as plain
  text unless `VERCEL_GIT_COMMIT_SHA` is set, which happens only when Vercel
  builds from the git integration and therefore proves the commit is on the
  remote. CLI deploys say "built from a working tree".
- The footer separator glyph measured **1.6:1**. Deleted rather than
  recoloured — a divider nobody can see is not a divider, and the footer already
  spaces its items.

## Also fixed in passing

`scripts/verifycontrast.py` raised `UnicodeEncodeError` on a cp1252 console
*after* all the browser work had finished, wasting the whole run on its last
print. It now rebinds stdout to UTF-8 rather than removing the glyphs, which are
the readable part of the output.

## Still open

- `packages/core/tests/testpib.py` resolves `benchmark/incidents/pib` relative to
  the cwd, so it silently loads zero scenarios and fails 8 tests unless pytest
  runs from the repo root. Pre-existing. `testbuildinfo.py` resolves from
  `__file__` deliberately, and says so.
- Next: **R58** (Start here), then **R59** closes Phase 5A.

See [[ObservatoryGrouping]] for the same verification pattern — two
independently computed values compared, rather than a checker grading its own
guess.
