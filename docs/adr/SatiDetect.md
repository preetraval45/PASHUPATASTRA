# Sati-Detect (Shailaputri) — does the learned detector earn its place?

- **Status:** Accepted · 18 October 2026 (RP-23; Claude, on the generated results)
- **Date:** 2026-10-18
- **Evidence:** [models/shailaputri.md](../research/models/shailaputri.md), train-sati run 39169841856

## Re-measured 26 October 2026 — decision unchanged, reasons changed

The 18 October table below used the harness's old false-alarm formula, which
left the normal points a detector did not flag out of the denominator, so it
read as 1000 × (1 − precision). The formula is fixed in
`pashupatastra.evaluation`. LightGBM now pins its thread count, after the same
code and data gave several different models across runs. Train-sati run
40366707718, mean across held-out families:

| Detector | F1 | Recall | False alarms / 1000 | Lead |
|---|---:|---:|---:|---:|
| **Shailaputri v0** | **0.382** | 0.711 | 26.6 | 180.2 |
| seasonal-robust-z | 0.312 | 0.761 | 74.7 | 241.3 |
| seasonal-naive | 0.346 | 0.930 | 74.7 | 240.0 |
| robust-z | 0.325 | 0.911 | 78.7 | 234.1 |
| EWMA | 0.261 | 0.900 | 14.2 | 229.0 |

- **False alarms: yes, now clearly.** It raises 26.6 per 1000 judged points
  against 74.7 for seasonal-robust-z. Only EWMA (14.2) is quieter, and EWMA has
  the lowest F1.
- **Lead time: no.** It flags at 180.2 points before an episode ends against
  241.3: later.
- **F1: still the best**, at 0.382. Its F1 was reported as 0.457 on
  18 October, and runs before the pin gave 0.382 or 0.424. That variance is
  the run-to-run non-determinism the pin removes.

**RP-23 requires both false alarms and lead time.** It now wins one and loses
the other, so the decision stands: `SeasonalRobustZ` stays the default and
Shailaputri is a second opinion. The reason is different from 18 October. Then
it tied on false alarms; now it wins them decisively and loses only on lead
time. Onset-weighted training raised F1 on SMD (0.531 → 0.556), but lead did
not improve there either (110.4 → 108.5), so earlier flags remain the open
problem.

### Across five training seeds (train-sati run 40391561511)

One run's numbers proved unreproducible across GitHub's runners, so
Shailaputri is now trained with seeds 7, 11, 13, 17 and 19 (CPU recorded:
AMD EPYC 7763). Mean [min, max]:

| Shailaputri v0 | Mean | Range | Best statistical detector |
|---|---:|---|---:|
| F1 | 0.435 | [0.382, 0.475] | 0.346 (seasonal-naive) |
| False alarms / 1000 | 25.6 | [23.3, 30.3] | 74.7 (seasonal-robust-z); EWMA 14.2 |
| Lead | 180.4 | [170.4, 190.2] | 241.3 (seasonal-robust-z) |

**The decision holds across every seed.** Even its worst seed beats every
statistical detector on F1 (0.382 against 0.346), and its noisiest seed raises
less than half seasonal-robust-z's false alarms (30.3 against 74.7). But its
earliest seed still flags later than seasonal-robust-z (190.2 against 241.3).
It wins on false alarms and loses on lead, so `SeasonalRobustZ` stays the
default and Shailaputri a second opinion, on evidence that no longer depends
on which machine ran the job.

*The 18 October measurement follows, kept as recorded and superseded by the
section above.*

## Context

Backlog item 2.1 said ML detection ships "only if it beats the best statistical
strategy on the benchmark", and RP-23 sharpened that: beating
`SeasonalRobustZ` on **false alarms per 1000 and lead time**, not only on F1.
Shailaputri v0 has now been trained and tested on NAB's 47 real series, with
each family held out in turn, and scored online by the same harness as the
four statistical strategies on exactly the same series.

## What the measurement found

Mean across held-out families:

| Detector | F1 | Recall | False alarms / 1000 | Lead |
|---|---:|---:|---:|---:|
| **Shailaputri v0** | **0.457** | 0.824 | 226.5 | 195.2 |
| seasonal-robust-z | 0.312 | 0.761 | 228.7 | 241.3 |
| seasonal-naive | 0.346 | 0.930 | 372.2 | 240.0 |
| robust-z | 0.325 | 0.911 | 656.5 | 234.1 |
| EWMA | 0.261 | 0.900 | 568.3 | 229.0 |

- **F1: yes, clearly.** It is the best of the five, and better than
  seasonal-robust-z by about 0.15.
- **False alarms: a tie.** 226.5 against 228.7 per 1000. It is no quieter than
  the quietest statistical detector, though it is far quieter than the other
  three.
- **Lead time: no.** About 46 points later than seasonal-robust-z, so it
  confirms an anomaly later in the window.
- **Absolute level:** every detector raises more than 200 false alarms per
  1000 points under NAB's window labelling. None of them should page a person
  on its own.

## Decision

**By RP-23's own test, the answer is "not yet".** Shailaputri v0 does not
beat seasonal-robust-z on lead time, and it only ties on false alarms.

- `SeasonalRobustZ` stays the default detector in `packages/core`.
- Shailaputri v0 is offered as a **second opinion**: it scores anomalies, and
  where it agrees with the statistical detector, that agreement raises
  confidence. It does not replace the statistical detector.
- Backlog 2.1 "ML detection" closes with this answer. A "no" closes the item,
  as RP-23 says.

## What would change it

- **Earlier flags.** Train on onset rather than whole-window membership. The
  label is currently "inside the window", which rewards confirming late.
- **SMD (multivariate)** as v1, where correlated metrics give a learned model
  something a univariate statistic cannot see.
- A threshold chosen for a **target false-alarm rate** rather than for F1.

## Consequences

**Enables:** an honest paper paragraph. A learned detector wins on F1 and
loses on timeliness, and here is why.

**Rules out:** claiming "ML detection beats statistics" from F1 alone.
