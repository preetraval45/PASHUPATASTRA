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
- **Out of scope:** closing incidents on its own. **No version yet may declare
  recovery unattended**; v1 + 3σ agreement comes closest (see v1 below).

## Data and split

SMD (Su et al., KDD 2019; MIT), 28 real servers. The data is 327 incidents
with an hour of clean history before them. Each incident is followed from
onset to 60 minutes after it ends. Leave one machine group out.

## Metrics (pooled over held-out groups)

| Verifier | Premature all-clear ↓ | Confirmed | Unconfirmed within the hour |
|---|---:|---:|---:|
| Mahagauri v0 | 0.220 | 0.590 | 0.190 |
| Back within 3σ of the pre-incident hour | 0.165 | 0.248 | 0.587 |
| Fixed timer (median training duration) | 0.480 | 0.520 | 0.000 |

## What the numbers say

- **The 5% budget did not generalise.** The threshold held premature
  all-clears to 5% on the training groups, but on held-out groups the rate is
  0.220: one incident in five is declared over while still labelled
  anomalous. This is the headline, and it is a negative result.
- **It confirms recovery more than twice as often as the hand-written
  check:** 0.590 against 0.248. The check is safer (0.165 premature) mainly
  because it rarely says anything: 0.587 of incidents stay unconfirmed.
- **A fixed timer is the worst on safety (0.480).** Incidents vary too much
  in length for any single wait to work.

## v1 (run 40514270660, 27 October 2026)

Two variants were measured beside v0, pooled over held-out groups:

| Verifier | Premature all-clear ↓ | Confirmed | Unconfirmed |
|---|---:|---:|---:|
| v0, point-estimate threshold | 0.220 | 0.590 | 0.190 |
| v1, upper-bound threshold | 0.144 | 0.498 | 0.358 |
| v1 + 3σ agreement | 0.070 | 0.223 | 0.707 |

- **Holding the upper bound helps but is not enough:** 0.144, still well above
  5%.
- **Requiring agreement with the 3σ check gets close to the budget (0.070),**
  at a price. It confirms only 0.223 of recoveries and leaves 0.707 to a
  human.
- **The trade-off is now explicit:** every step toward safety hands more
  incidents back to people. For a verifier that is the right direction to
  err, so **v1 + 3σ agreement is the variant to serve**. Even so, it is not
  yet within budget, and it must not close incidents unattended.

## Known limitations and what would fix them

- **Labels are the operators' judgement.** SMD marks when operators
  considered each anomaly over, and some "premature" calls may be right
  early.
- **The budget is a point estimate.** A threshold that sits exactly at 5% on training data drifts above it on new machines. v1 tried both remedies, an upper-bound threshold and 3σ agreement (above). Agreement comes closest; a calibrated recovery probability would be the next step.

## Ethical considerations

Server metrics only. There is no personal data.
