# Retrain only what changed

**Date:** 2026-10-27

## Why
Every push touching packages/sati retrained all eleven model jobs. LightGBM is `deterministic` with fixed threads, but runner CPUs differ, so each retrain moved published numbers by a few hundredths. That staled the paper §7.2 and the model cards (Shailaputri, Siddhidatri) twice in a day.

## Decisions
- train-sati.yml has a `changes` job (dorny/paths-filter). Each model job runs only when its own code or data changed, or on a manual dispatch. Shared: sati/sources and pyproject.
- kaggle-kushmanda.yml triggers only on the training files, not all of sati/lm (constrained decoding and infer live there).
- rcaeval-diagnosis.yml no longer triggers on its own file. Editing the table step reran ~5 h of LLM jobs once (27 Oct).

## Next session
- To refresh every table deliberately: dispatch train-sati.yml, then run `reproduce.py` and update the paper/cards in the same change.
