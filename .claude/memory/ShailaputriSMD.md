# Shailaputri v1 on SMD (RP-60)

- **Date:** 2026-10-26
- **Phase:** Block H — Real-data models
- **Commit(s):** pending

## What changed

Added the SMD loader, the multivariate run module `sati.detect.smd`, its
report `smdreport`, 5 tests and a `shailaputri-smd` CI job. `reproduce.py` now
lists full report module paths.

## Why

RP-60's remaining items were SMD and earlier flags. SMD has 38 metrics per
machine and labels per minute, while v0's features are univariate.

## Decisions made

- **Features transfer across machines.** Per-metric causal features are
  aggregated across a machine's metrics, so the model reads "how unusual is
  this server now" the same way on any machine.
- **Unlabelled first halves are never training targets.** They serve only as
  feature history and as PCA fitting data. The report notes that this
  favours the PCA baseline.
- **Onset weighting is a measured variant.** It is reported as its own row and
  is not the default.

## Next session should

- Read the first SMD run. Judge onset weighting by lead and false alarms, not
  by F1 alone.
- Add the SMD results to the Models page.
