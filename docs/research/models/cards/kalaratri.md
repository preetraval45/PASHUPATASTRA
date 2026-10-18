# Model card — Kalaratri v0 (`sati-kalaratri-v0`)

Format follows Mitchell et al. (2019). The generated table
[kalaratri.md](../kalaratri.md) is the source of truth.

## Model details

- **What it does:** flags anomalous HDFS blocks from the sequence of log
  templates each block produced. Model 7 of the nine Sati models
  ([adr/Navadurga](../../../adr/Navadurga.md)).
- **Type:** a LightGBM binary classifier. Its inputs are:
  - per-template counts, with the vocabulary taken from training blocks only;
  - a count of templates never seen in training;
  - the sequence length and the share of distinct templates.

  The threshold is chosen on a validation slice that comes later in time than
  the training data.
- **Built by:** an AI assistant (Claude), under the owner's direction.
- **Weights: not published.** LogHub is licensed for research or academic use
  only ([datasheets.md](../../datasheets.md)), and how such weights may be
  released is the owner's decision.

## Intended use

- **Research and evaluation:** a learned log-anomaly detector compared with the
  classic PCA method on the dataset that method was first published on.
- **Out of scope:** production alerting on other systems' logs. It has only
  seen Hadoop's log templates.

## Data and split

LogHub HDFS_v1: 575,061 blocks, 2.93% anomalous, labelled by the original
study (Xu et al., SOSP 2009). The split is **by time**: the first 60% train,
the next 20% set the threshold, and the last 20% test. It is never shuffled.

## Metrics (snapshot, run 39170294506; test = the last 115,013 blocks)

| Detector | Precision | Recall | F1 | False-positive rate |
|---|---:|---:|---:|---:|
| Kalaratri v0 | 1.000 | 0.934 | 0.966 | 0.0000 |
| PCA (Xu et al. 2009) | 0.766 | 0.996 | 0.866 | 0.0045 |
| Never-seen-template rule | 1.000 | 0.432 | 0.604 | 0.0000 |

## Known limitations

- **HDFS is an easy benchmark.** Many blocks share identical template
  sequences, so recognising sequences seen before is much of the task. That
  is legitimate in deployment, where the same sequences recur, but it makes
  HDFS a weak test of generalisation. BGL, a harder and more varied log, is
  next.
- **It relies most on block shape** (distinct-template share and length) and
  on a few templates (E26, E2, E4). A system whose failures do not change the
  shape of the log would be harder.
- **It misses 6.6% of anomalous blocks**, while PCA misses almost none. Which
  matters more depends on the cost of a missed failure versus a false alarm.

## Ethical considerations

Logs can carry personal data. Only template ids and counts are used here, never
log text.
