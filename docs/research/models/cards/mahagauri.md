# Model card — Mahagauri v0 (`sati-mahagauri-v0`)

Format follows Mitchell et al. (2019). The generated table
[mahagauri.md](../mahagauri.md) is the source of truth. The numbers below
are a snapshot of training run 40360156287 (26 October 2026).

## Model details

- **What it does:** decides, once a minute after an incident starts, whether
  a server has returned to normal. It declares *all clear* after three
  consecutive yeses. Model 8 of the nine
  ([adr/Navadurga](../../../adr/Navadurga.md)): the Verify step of the loop,
  which engineering rule 3 makes compare observed state with expected state.
- **Type:** LightGBM over these inputs:
  - Shailaputri's causal features, aggregated across a server's 38 metrics;
  - each metric's distance from its own pre-incident hour (max, mean, and
    the count beyond 3σ);
  - minutes since onset.

  The threshold is the lowest that keeps premature all-clears at or below 5%
  on the training groups.
- **Built by:** an AI assistant (Claude), under the owner's direction.

## Intended use

- **For:** research. In particular, it measures how hard "is it really over?"
  is on real servers.
- **Out of scope:** closing incidents on its own. **This version must not be
  trusted to declare recovery** (see the metrics).

## Data and split

SMD (Su et al., KDD 2019; MIT), 28 real servers. The data is 327 incidents
with an hour of clean history before them. Each incident is followed from
onset to 60 minutes after it ends. Leave one machine group out.

## Metrics (pooled over held-out groups)

| Verifier | Premature all-clear ↓ | Confirmed | Unconfirmed within the hour |
|---|---:|---:|---:|
| Mahagauri v0 | 0.199 | 0.560 | 0.242 |
| Back within 3σ of the pre-incident hour | 0.165 | 0.248 | 0.587 |
| Fixed timer (median training duration) | 0.480 | 0.520 | 0.000 |

## What the numbers say

- **The 5% budget did not generalise.** The threshold held premature
  all-clears to 5% on the training groups, but on held-out groups the rate is
  0.199: one incident in five is declared over while still labelled
  anomalous. This is the headline, and it is a negative result.
- **It confirms recovery more than twice as often as the hand-written
  check:** 0.560 against 0.248. The check is safer (0.165 premature) mainly
  because it rarely says anything: 0.587 of incidents stay unconfirmed.
- **A fixed timer is the worst on safety (0.480).** Incidents vary too much
  in length for any single wait to work.

## Known limitations and what would fix them

- **Labels are the operators' judgement.** SMD marks when operators
  considered each anomaly over, and some "premature" calls may be right
  early.
- **The budget is a point estimate.** A threshold chosen to sit exactly at
  5% on training data will drift above it on new machines. v1 should set
  the threshold for an upper confidence bound on the premature rate, not its
  point estimate, or require agreement with the 3σ check before declaring
  recovery.

## Ethical considerations

Server metrics only. There is no personal data.
