# Shailaputri

- **Date:** 2026-10-18
- **Phase:** Block H — RP-60 (also covers RP-21 and RP-22 for NAB)
- **Commit(s):** this push

## What changed

- packages/sati/sati/sources/nab.py loads only the real NAB families, pinned to
  a commit.
- packages/sati/sati/detect/ holds features.py (causal: rolling stats are
  shifted by 1, windows 12/72/288, diff, volatility, season), model.py
  (LightGBM binary, plus a Replay strategy for the core evaluate()), run.py
  (leave-one-family-out against the 4 core strategies) and report.py.
- packages/sati now depends on pashupatastra-core, and CI installs both.
- train-sati.yml has a `shailaputri` job that commits
  docs/research/models/shailaputri.* and apps/web/lib/models/shailaputri.results.json.
- The Models page uses statusOf() and shows the Shailaputri section once
  results exist (the placeholder has `pending`).

## Decisions made

- Features are computed for the whole series at once, but they are causal, so
  this is equivalent to running online. A test proves no look-ahead.
- The threshold is chosen from 0.30 to 0.95 on training families only.

## Next session should

- Read the run's table. Then SMD (multivariate) as v1, then Chandraghanta and
  Kalaratri once the owner decides on the research-only licences.
