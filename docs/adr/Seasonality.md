# ADR — Seasonality in statistical detection

**Status:** Accepted · 17 August 2026
**Supersedes the framing in:** [ROADMAP.md](../ROADMAP.md) §2.1
**Evidence:** `scripts/benchdetect.py`, 8 tests in `packages/core/tests/testevaluation.py`

## Context

The roadmap recorded a blocking gap:

> The shipped robust-z default scores 859 false alarms per 1000 on a daily-shaped
> series; EWMA scores 43. A detector that cries wolf every morning is one
> operators learn to ignore.

It marked this a hard gate on Phase 9 security detection, and correctly so —
human activity is the most seasonal signal there is, so a security detector
inheriting a seasonality bug inherits it on every metric that matters.

We re-ran the comparison across six workload shapes before changing anything.
The gap is real. **The diagnosis in that sentence is not.**

## What the measurement found

### 1. The 859 figure is an artifact of the test fixture

The existing seasonal fixture is a **square wave** — an instantaneous step up and
down each cycle. Against a smooth sine of the same amplitude:

| Workload | robust-z | ewma | seasonal-naive | seasonal-robust-z |
|---|---|---|---|---|
| seasonal, square | **901.5** | 47.6 | 0.0 | 0.0 |
| seasonal, sine | **0.0** | 0.0 | 0.0 | 0.0 |

Real traffic ramps; it does not teleport. On the realistic shape robust-z emits
**zero** false alarms, and a fix aimed at its noisiness would have been aimed at
a fixture rather than at the system.

### 2. The real cost of seasonality is blindness, not noise

Robust-z scores zero on the sine workload for a bad reason. Seasonal spread
inflates MAD until the threshold band is wider than the data:

```
series spans        38.5 .. 101.8
3-sigma band       -26.3 .. 156.8
```

Nothing inside that band can ever fire, however wrong it is. Sweeping a genuine
incident by magnitude, against a series peaking near 100:

| Smallest spike detected | Strategy |
|---|---|
| 110 | seasonal-robust-z, seasonal-naive |
| 130 | ewma |
| **180** | **robust-z** |

Robust-z needs an incident at nearly twice the normal peak before it reacts.
Every smaller genuine problem passes as `NORMAL`.

**This is the more dangerous failure, and it is why the original framing
mattered.** A flood of false alarms is visible and irritating; an over-wide band
is silent, and silence is indistinguishable from an all-clear. Optimising for the
reported metric — false alarms per 1000 — would have selected *for* blindness.

### 3. Seasonal-naive echoes every incident

`SeasonalNaive` compares against the same point one cycle back, so an incident
becomes its own expectation one period later. Measured: an incident at samples
300–309 produced a phantom at 360–369, exactly one period on. Its precision is
pinned at 0.50 by construction, whatever its detection quality.

## Decision

### 1. Add `SeasonalRobustZ`, and do not make it the default

A per-phase median estimates what this point in the cycle normally looks like;
robust statistics are applied to the residual. The band then reflects the
metric's actual noise rather than its daily range. A median across five cycles
has no echo, because one contaminated cycle cannot move it.

It wins every workload — 0.0 worst-case false alarms, detection down to 110 —
**when it is told the right period.** It is still not the default, because of two
measurements that the roadmap's task line ("change the default strategy") did not
anticipate:

| Configured period (true period 60) | Detects spike at 130 | Detects spike at 200 |
|---|---|---|
| 60 | yes | yes |
| 45 | no | yes |
| 90 | no | yes |
| **30** | **no** | **no** |

A wrong period does not make it noisy. It makes it **blind**, which is the exact
failure we are trying to remove, now with no false alarms to reveal it.

And warm-up is three full cycles: 200 samples at period 60, **884** at period
288. On a non-seasonal series with `period=288` configured, it missed a 30-sample
outage entirely because the outage fell inside its warm-up. Robust-z caught the
same outage with precision 1.00.

Production does not know the period of an arbitrary `(entity, metric)` pair.
Guessing one risks silent blindness on every metric we guess wrong.

**Therefore:** robust-z stays the default. `SeasonalRobustZ` is opt-in, per
metric, where the period is known — never inferred.

### 2. Report mis-specification, since we are not fixing it globally

Keeping robust-z as the default keeps its blindness on seasonal metrics. That is
only acceptable if the blindness is *visible*, so `Baseline` now measures whether
its own assumption holds.

Both failure modes are one broken assumption. A baseline assumes samples scatter
independently around a stable median; seasonality, trend and drift all violate
that. A series with shape barely moves between consecutive samples while ranging
widely overall — so spread ÷ volatility separates them cleanly:

| Series | ratio | |
|---|---|---|
| flat noise | 0.96 | healthy |
| flat noise, wide | 0.73 | healthy |
| flat + one outage | 0.78 | healthy |
| pure trend | 2.55 | mis-specified |
| random walk | 2.53 | mis-specified |
| seasonal square | 1.93 | mis-specified |
| seasonal sine | 10.08 | mis-specified |

The cut is **1.5**, chosen from the empty space between the groups rather than
balanced on either edge. `Detector.warmup()` now reports `unmodelled` beside
`warm`, and `unmodelled_keys()` names them — those are precisely the metrics that
should be moved to `SeasonalRobustZ` with a known period.

This deliberately extends the existing rule that a cold baseline reports
`UNKNOWN` and never `NORMAL`. A cold detector is silent and admits it. A
mis-specified one speaks with full confidence, which is worse.

## Consequences

**Good.** The Phase 9 gate is cleared with the failure understood rather than
worked around. Blindness — silent, and previously invisible to every metric we
had — is now reported. The correct strategy exists and is benchmarked.

**Costs.** Seasonal metrics are still on robust-z by default and still blind
until someone acts on `unmodelled`. This ADR trades an automatic fix for a
visible problem, deliberately: a wrong automatic period would be an invisible
one.

**Owed.** Period detection by autocorrelation would make the opt-in automatic and
safe. It is Phase 5 work — it needs the benchmark's labelled scenarios to
validate against, and shipping it on judgement is how we got here.

**Guard.** `scripts/benchdetect.py --strict` runs in CI and fails if the recorded
recommendation stops winning.

## Alternatives rejected

**Make EWMA the default.** It is second on both axes — 47.6 worst-case false
alarms, detection at 130 — and it absorbs sustained outages by design, which is
the incumbent's whole advantage and is already covered by a test.

**Make seasonal-naive the default.** Its echo pins precision at 0.50.

**Tune robust-z's threshold.** Threshold changes trade the two failure modes
against each other along one axis. The problem is that the model is wrong for the
data, and no threshold fixes a band centred on the wrong shape.

**Fix the square-wave fixture and declare the gap closed.** Tempting, since the
headline number came from it. It would have hidden a worse bug: the fixture
was misleading, but robust-z on seasonal data is genuinely broken — just
silently, in the opposite direction.
