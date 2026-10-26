# Mahagauri and Skandamata built (RP-71, RP-72)

- **Date:** 2026-10-26
- **Phase:** Block H — Real-data models
- **Commit(s):** pending

## What changed

Added two of the three remaining Navadurga models, each on real data, with a
CI job and tests:

- **Mahagauri** (`sati.verify`) verifies recovery on SMD's real incidents.
- **Skandamata** (`sati.respond`) maps a behaviour to ATT&CK mitigations.

## Why

The owner asked for every Navadurga model, for bigger work and for more
notebooks. Both models reuse existing loaders: SMD for Mahagauri, ATT&CK and
Brahmacharini's source split for Skandamata.

## Decisions made

- **Mahagauri's headline is the premature all-clear rate.** That is the
  dangerous error. Its thresholds are set on the training groups, capping it
  at 5%.
- **Skandamata is a multi-label classifier, not retrieval.** ATT&CK has only
  about 44 mitigations, a small fixed label set. Popularity is a hard baseline
  for it and is reported first.

## Next session should

- Read both first runs, then write the cards and Models page sections.
- Build Siddhidatri (fusion and calibration).
- Write notebooks 06 onward.

## Follow-up

- **Siddhidatri (RP-73)** is built: out-of-fold stacked logistic fusion on
  SMD, measured by ECE and Brier.
- **Gitleaks false positive.** It flagged a cache `key:` value in
  train-sati.yml (generic-api-key). The cache keys are renamed to plain
  words; keep hex and versioned slugs out of `key:` lines.

## Results (26 Oct, run 40360156287)

- **Skandamata:** hit@1 0.775 against BM25 two-hop 0.541. Strong. RP-72
  is ticked; it has a card and a Models page section.
- **Mahagauri:** a negative result. 0.199 premature all-clears on held-out
  groups, against a 5% budget on training. RP-71 is ticked with that stated;
  the card says do not trust it to declare recovery. The v1 idea: a
  threshold set on an upper confidence bound, or agreement with the 3σ
  check.

## Mahagauri v1 (26 Oct)

Two rows were added beside v0: an upper-bound threshold (one-sided Wilson 95%
bound within 5%), and the same plus 3σ agreement. Judge them on the premature
rate first, then on the confirmed rate. Account security is done by the
owner: the old key was deactivated, the password changed and MFA enabled.
