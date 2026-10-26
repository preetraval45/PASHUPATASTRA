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
