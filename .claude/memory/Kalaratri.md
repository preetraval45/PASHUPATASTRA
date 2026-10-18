# Kalaratri

- **Date:** 2026-10-18
- **Phase:** Block H — RP-62
- **Commit(s):** this push

## What changed

- packages/sati/sati/sources/loghub.py downloads HDFS_v1.zip (186 MB) and reads
  Event_traces.csv plus anomaly_label.csv from the archive. Columns are found
  by name pattern, because the preprocessed CSV's headers are not pinned.
- packages/sati/sati/loganomaly/run.py: features are template counts from a
  training-only vocabulary, plus unseen/length/distinct share. The model is
  LightGBM with scale_pos_weight. Split is by time, 60/20/20 in log order,
  with the threshold set on validation. Baselines are PCA and the
  unseen-template rule.
- train-sati.yml has a `kalaratri` job that commits metrics only and
  uploads no weights artifact.
- The Models page shows a Kalaratri section once results exist.

## Decisions made

- Research-only data means no weights artifact. In a public repo, artifacts
  are effectively published, so the owner decides first.
- Row order in Event_traces is taken as time order. That is an assumption,
  and it is stated in the code.

## Next session should

- If the run fails on CSV parsing, read the job log; the column detection is
  heuristic. Then do BGL.
