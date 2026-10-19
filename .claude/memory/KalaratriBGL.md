# Kalaratri on BGL, and the notebook lint failure

- **Date:** 2026-10-18
- **Phase:** Block H — Real-data models (RP-62)
- **Commit(s):** 6135061, 812e5ae

## What changed

`python -m sati.loganomaly.run --dataset bgl` trains Kalaratri on LogHub BGL, which has 4.7M lines and comes from the same Zenodo record as HDFS. The `kalaratri` job now runs both HDFS and BGL. Separately, the model notebooks failed the `Train Sati models / test` job on lint (E401, E402, E701, E702), which blocked every training job. Commit 6135061 fixed them.

## Why

RP-62 still needed BGL. HDFS is an easy benchmark: blocks repeat, so recognising sequences already seen does most of the work. BGL is the harder test.

## Decisions made

- BGL ships raw log lines with no template ids. A template is the message with every token that contains a digit masked. The severity level is left out.
- Data is cut into fixed windows of 100 consecutive lines; a window is anomalous if any of its lines has a label. The same 60/20/20 time split is used, with the same baselines.
- BGL features use float32, because its vocabulary is much wider than HDFS's. HDFS keeps float64, so its committed table still reproduces byte-for-byte.
- Lint notebooks with CI's ruff (<0.13) before pushing. Local ruff 0.16 reports different rules.
  Command: `pip install --target <scratch>/ruff12 "ruff<0.13"`.

## Next session should

- After the `kalaratri` job publishes `kalaratri-bgl.md`, write the BGL section of the Kalaratri card and tick RP-62 if the results warrant it.
- If BGL runs out of memory or time on the runner, cut the vocabulary to templates seen at least twice in training.
