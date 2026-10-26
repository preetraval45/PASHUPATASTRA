# False alarms per 1000 was 1000 × (1 − precision)

- **Date:** 2026-10-26
- **Phase:** Block H — Real-data models (RP-74)
- **Commit(s):** pending

## What changed

`Score.false_alarms_per_1000` now divides by `judged_samples`: every
non-warm-up reading. Before, `evaluate()` never counted unflagged normal
readings, so the denominator was the flagged points plus warm-up.

## Why

The SMD report showed precision 0.617 next to 383 false alarms per 1000.
Those cannot both hold when anomalies are about 4% of minutes, and the
contradiction exposed the bug.

## Decisions made

- **Historical quotes are kept, with notes.** The Seasonality ADR still
  quotes the old roadmap's "859"; a dated note gives the corrected 397.8 and
  says the decision is unchanged.
- **SatiDetect is flagged for re-measurement.** Its "ties on false alarms"
  comparison used the old formula, and the decision is re-checked once the
  rerun lands.
- **Retraining follows the harness.** `train-sati.yml` now also triggers on
  `packages/core/pashupatastra/evaluation.py`.
- **Siddhidatri thresholds** come from quantiles of the out-of-fold
  probabilities. The fixed 0.3–0.95 grid made calibrated single detectors
  never flag anything.

## Next session should

- When the rerun lands, update adr/SatiDetect with the corrected numbers,
  keep or flip its decision, and refresh the Shailaputri and SMD cards and
  §8 material.
