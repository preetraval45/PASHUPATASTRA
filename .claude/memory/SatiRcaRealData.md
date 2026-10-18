# SatiRcaRealData

- **Date:** 2026-10-18
- **Phase:** Block H — RP-58 (Sati-RCA v0 on RCAEval)
- **Commit(s):** this push

## What changed

- The owner reversed model ownership. Claude now builds and trains every Sati
  model on real public data, and all of Sati's AI should be the project's own.
  Recorded in adr/RealDataModels.md and as plan Block H (RP-58 to RP-65).
- packages/sati, the first model:
  - `sources/rcaeval.py` downloads RCAEval from Hugging Face, pinned to the dataset
    commit.
  - `rca/features.py` computes per-service robust shift, peak and onset for each
    metric family (cpu, mem, latency, traffic, error, other). Values are
    log-compressed and ranked within the incident, and each one records the
    series it came from.
  - `rca/model.py` is a LightGBM lambdarank with pre-declared params, plus a
    baseline that ranks by largest shift with no learning.
  - `rca/run.py` runs the splits: leave-one-system-out, held-out fault and
    held-out repetition on RE1+RE2. RE3 is a stress test and is never trained on.
  - `rca/report.py` generates the markdown table.
- `.github/workflows/train-sati.yml` runs tests, then training, then commits
  docs/research/models/sati-rca.md and the results JSON. The model ships as a
  workflow artifact.

## Why

The owner asked for "real models, trained on real-life data and tested on it",
with all AI their own and nothing run on their PC. RCAEval is the closest real
data to Sati-RCA's job: a root-cause-service label, metrics, and three systems,
which is what makes leave-one-system-out possible.

## Decisions made

- Ranker over service features, not a classifier over service names. A name
  classifier can't transfer to an unseen system.
- No incident-size feature, because it fingerprints the system.
- RCAEval stopped being the zero-shot external benchmark once it became
  training data. RP-33 needs a different benchmark.
- No local smoke run on real data (owner's rule). The first real run is the CI
  run.

## Next session should

- Read the first `train-sati` run. If it fails, check the job log. If it
  succeeds, review docs/research/models/sati-rca.md, then tick RP-58 or record
  what's wrong.
- RP-59 datasheets, then RP-60, RP-61 and RP-62 detection models, then RP-63
  serving.
