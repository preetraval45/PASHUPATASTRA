# Model card — Siddhidatri v0 (`sati-siddhidatri-v0`)

Format follows Mitchell et al. (2019). The generated table
[siddhidatri.md](../siddhidatri.md) is the source of truth. The numbers below
are a snapshot of train-sati run 40366707718 (26 October 2026), after the
threshold fix.

## Model details

- **What it does:** combines three detectors' scores into one probability
  that a server is anomalous this minute. Model 9 of the nine
  ([adr/Navadurga](../../../adr/Navadurga.md)): the one that combines the
  others.
- **Type:** a logistic regression (numpy, Newton's method) over Shailaputri
  v1, max robust z and per-machine PCA. Its weights are learned on
  Shailaputri's **out-of-fold** scores inside the training groups, never on a
  model's scores on its own training data. Thresholds come from quantiles of
  the out-of-fold probabilities.
- **Built by:** an AI assistant (Claude), under the owner's direction.

## Data and split

SMD, 28 real servers, leave one machine group out (as
[shailaputri-smd](shailaputri-smd.md)). Each single detector also gets its own
logistic calibration, so every row in the table states a probability.

## Metrics (mean across held-out groups)

| Verdict from | F1 | Episode recall | False alarms / 1000 | ECE ↓ | Brier ↓ |
|---|---:|---:|---:|---:|---:|
| Siddhidatri v0 (fused) | 0.534 | 0.768 | 47.9 | 0.0419 | 0.0571 |
| Shailaputri alone, calibrated | 0.530 | 0.590 | 4.0 | 0.0183 | 0.0415 |
| PCA alone, calibrated | 0.416 | 0.724 | 84.5 | 0.0422 | 0.0582 |
| Max robust z alone, calibrated | 0.253 | 0.778 | 20.4 | 0.0183 | 0.0420 |

## What the numbers say

**Fusion did not earn its place on SMD.**

- Its F1 equals Shailaputri's alone (0.534 against 0.530).
- It catches more episodes (recall 0.768 against 0.590), but raises false
  alarms twelve-fold (47.9 against 4.0).
- It is **worse calibrated** (ECE 0.042 against 0.018).

The weights put most trust in Shailaputri, and the other two add mostly
noise. The fusion moves the operating point toward recall rather than making
a better verdict. A verdict-maker earns its place when its inputs disagree in
useful ways. Here, as Chandraghanta's results showed for network detectors,
that would need detectors that fail on different incidents, not
three views of the same metrics.

## Known limitations

One dataset, three inputs, all metric-based. The fusion design is
input-agnostic. Fusing log (Kalaratri) and network (Chandraghanta) verdicts
needs incidents labelled across those sources, which no public dataset here
has.
