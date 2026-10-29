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
| Siddhidatri v0 (fused) | 0.537 | 0.774 | 47.8 | 0.0419 | 0.0571 |
| Shailaputri alone, calibrated | 0.539 | 0.597 | 3.8 | 0.0182 | 0.0415 |
| PCA alone, calibrated | 0.416 | 0.724 | 84.5 | 0.0422 | 0.0582 |
| Max robust z alone, calibrated | 0.253 | 0.778 | 20.4 | 0.0183 | 0.0420 |

*Copied from the generated table at run 40577370883 (27 Oct). LightGBM on CI's shared CPUs moves these
by a few hundredths between runs; the generated table is authoritative.*

## What the numbers say

**Fusion did not earn its place on SMD.**

- Its F1 equals Shailaputri's alone (0.537 against 0.539).
- It catches more episodes (recall 0.774 against 0.597), but raises false
  alarms twelve-fold (47.8 against 3.8).
- It is **worse calibrated** (ECE 0.042 against 0.018).

The weights put most trust in Shailaputri, and the other two add mostly
noise. The fusion moves the operating point toward recall rather than making
a better verdict. A verdict-maker earns its place when its inputs disagree in
useful ways. Here, as Chandraghanta's results showed for network detectors,
that would need detectors that fail on different incidents, not
three views of the same metrics.


## v1 (run 40577370883, 27 October 2026): fusion at Shailaputri's false-alarm rate

v1 held the fused threshold to Shailaputri's own false-alarm rate on the
training groups' out-of-fold scores, to ask whether fusion catches more at the
same cost. It does not. On held-out groups it scores F1 0.505 with 37.5 false
alarms per 1000, against Shailaputri's 0.539 and 3.8. The budget set on the
training groups does not hold on unseen machines, so fusion stays a recorded
negative and Shailaputri alone is the detector to use.

## Known limitations

One dataset, three inputs, all metric-based. The fusion design is
input-agnostic. Fusing log (Kalaratri) and network (Chandraghanta) verdicts
needs incidents labelled across those sources, which no public dataset here
has.
