# Block B started: Kaal generator (RP-17) and dataset v1 (RP-18)

- **Date:** 2026-10-26
- **Phase:** Block B — Ground truth and training data
- **Commit(s):** pending

## What changed

- **`adr/KaalGenerator.md`.** The fault model is **Proposed**: drafted by
  Claude, awaiting the owner's decision.
- **`pashupatastra.kaal.generator` and `generate`.** Deterministic synthetic
  incidents: Drishti Events plus a label.
- **`pashupatastra.kaal.dataset`.** Splits, a contamination guard, and a
  committed manifest at `docs/research/datasets/kaal-v1.json` (50k
  incidents, seed 1).
- **CI.** The core job regenerates the manifest and fails on any difference.

## Why

The owner asked to start Block B. RP-17 assigns the fault-model design to the
owner, so it is drafted as a proposal and RP-17 stays `[~]`. RP-13's answer
keys (the 20 incidents) are the owner's and are not touched.

## Decisions made

- **Event ids** come from the incident id plus position, not ULIDs, so output
  is byte-identical per seed.
- **Test repeats are dropped and counted.** Test incidents whose structural
  signature repeats a training one are removed, not treated as a failure
  (14 of 50k).
- **Held-out faults:** `cpu_saturation` (an unseen fault in a seen category)
  and `consumer_lag` (an unseen category). Holding out `packet_loss` would
  have removed the network category from training entirely.
- **The 50k dataset is not committed.** It is about 260 MB and regenerates
  in seconds. The manifest is the contract.

## Next session should

- **Owner:** decide the ADR. If the fault model changes, regenerate the
  manifest in a deliberate commit.
- **RP-24:** a Sati-RCA ranker trained on Kaal train, evaluated on test-id,
  test-ood-topology and test-ood-fault, and on RCAEval as sim-to-real.
