# Model card — Kalaratri v0 (`sati-kalaratri-v0`)

Format follows Mitchell et al. (2019). The generated table
[kalaratri.md](../kalaratri.md) is the source of truth.

## Model details

- **What it does:** flags anomalous HDFS blocks (and BGL windows, below) from the sequence of log
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

## BGL, the harder test

The generated table [kalaratri-bgl.md](../kalaratri-bgl.md) is the source of
truth. These are the run 40347301393 figures.

**Data.** LogHub BGL has 4.7M lines from the BlueGene/L supercomputer, each
labelled by its administrators (Oliner and Stearley, DSN 2007). There are no
blocks, so the data is cut into 47,134 windows of 100 consecutive lines. A
window counts as anomalous if any of its lines has a label, which makes 10.2%
of windows anomalous.

**Templates.** These come from the message text with every token that contains
a digit masked. The severity level is not used. Training windows contain 310
distinct templates.

**Split.** The same time split as HDFS, never shuffled. The test set is the
last 9,427 windows.

| Detector | Precision | Recall | F1 | False-positive rate |
|---|---:|---:|---:|---:|
| Kalaratri v0 | 0.513 | 0.271 | 0.355 | 0.024 |
| PCA (Xu et al. 2009) | 0.092 | 0.829 | 0.166 | 0.772 |
| Never-seen-template rule | 0.098 | 1.000 | 0.179 | 0.870 |

- **Twice the baselines' F1, but it misses most failures.** It finds 27% of
  anomalous windows, and about half of what it flags is real. The two
  baselines reach high recall only by flagging 77–87% of normal windows,
  which makes them unusable as alerts.
- **Later months bring new failures.** Under a time split, the alert types in
  the test period are partly absent from training. That is the case a
  deployed detector meets, and it is why random-split BGL results are much
  higher.
- **Template masking is crude.** Messages that differ only in a word with no
  digit stay separate templates. A learned parser such as Drain is the
  obvious next step, and it should be measured before it is assumed better.
- **Novelty features buy precision, not recall** (run 40797786556). The
  "unseen in training" count is zero on every training window, so no model
  can learn from it. v1 adds causal counts instead: lines whose template never
  appeared earlier in the log, and lines whose template is still rare. On BGL,
  precision rises from 0.513 to 0.778 and the false-positive rate falls from
  0.0244 to 0.0059, but recall falls to 0.220 and F1 to 0.343. On HDFS, F1
  moves from 0.966 to 0.968. New failure types in later months are not mostly
  first-seen templates, so the recall gap remains. v0 stays served.

## Ethical considerations

Logs can carry personal data. Only template ids and counts are used here, never
log text.
