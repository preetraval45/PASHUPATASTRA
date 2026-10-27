# Model card — Shailaputri v1 on SMD (`sati-shailaputri-v1`)

Format follows Mitchell et al. (2019). The generated table
[shailaputri-smd.md](../shailaputri-smd.md) is the source of truth. The
numbers below are a snapshot of train-sati run 40366707718 (26 October 2026),
with the corrected false-alarm rate and pinned LightGBM threads.

## Model details

- **What it does:** flags the minutes when a server is anomalous, judged
  across all 38 of its metrics. Model 1 of the nine
  ([adr/Navadurga](../../../adr/Navadurga.md)), on its second dataset.
- **Type:** LightGBM over Shailaputri's causal per-metric features, aggregated
  across a server's metrics each minute: the largest and the mean absolute
  deviation, and how many metrics deviate strongly. An **onset-weighted**
  variant gives the first 20% of each anomaly five times the training weight.
- **Built by:** an AI assistant (Claude), under the owner's direction.

## Data and split

SMD (Su et al., KDD 2019; MIT): 28 real servers, with 708,420 labelled test
minutes and 327 anomalies. **Leave one machine group out:** trained and tuned
on two groups, tested on the third. Each server's unlabelled first half is
used only as feature history and for the PCA baseline.

## Metrics (mean across held-out groups)

| Detector | F1 | Precision | Episode recall | False alarms / 1000 | Lead |
|---|---:|---:|---:|---:|---:|
| Shailaputri v1, onset-weighted | 0.564 | 0.617 | 0.643 | 4.6 | 106.9 |
| Shailaputri v1 | 0.525 | 0.611 | 0.601 | 4.5 | 122.0 |
| PCA per machine | 0.419 | 0.426 | 0.728 | 86.6 | 101.1 |
| Max robust z | 0.279 | 0.188 | 0.798 | 18.0 | 105.8 |

*Copied from the generated table at run 40406026750 (27 Oct). LightGBM on CI's shared CPUs moves these
by a few hundredths between runs; the generated table is authoritative.*

## What the numbers say

- **It is the best and the quietest:** F1 0.525–0.564 against 0.419, and
  4.5–4.6 false alarms per 1000 minutes against 18.0 and 86.6. That pairing is
  what makes an alert worth reading.
- **It misses more episodes than the baselines** (recall 0.60–0.64 against
  0.73–0.80). Its precision is bought with recall.
- **Onset weighting raised F1 but did not bring flags earlier** (lead 106.9
  against 122.0). The "earlier flags" goal of RP-60 is not met by
  re-weighting; it needs different features.

## Known limitations

SMD's labels are the operators' judgement, and some "missed" episodes may be
unremarkable in the metrics. Scoring is event-level, never point-adjusted,
which keeps the numbers lower than much of the literature (datasheets.md).
