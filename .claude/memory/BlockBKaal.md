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

## RP-24 and generator v1 (same day)

- **Katyayani on Kaal** (`sati.rca.kaal`): RCA@1 was 1.000 on v0 on every
  split, and the simulator was the reason. v1 added five realism knobs
  (ADR §v1). The ranker stays at about 0.998 while the baselines drop to
  0.46–0.75.
- **I stopped tuning the simulator to taste on purpose.** A synthetic score
  isn't the claim; sim-to-real on RCAEval is.
- **The manifest was regenerated deliberately for v1.** Counts are
  unchanged.
- **Next:** convert RCAEval cases into Kaal-style events, then run the
  Kaal-trained ranker on them zero-shot.

## Sim-to-real (same day)

- `sati.rca.simtoreal` runs the Kaal-trained ranker zero-shot on RCAEval
  Online Boutique and Sock Shop. Call graphs are authored in `GRAPHS`, and
  Train Ticket is excluded.
- A 12-case smoke run showed a large gap. The full numbers come from the
  `katyayani-simtoreal` CI job.
- **Next:** verify the authored graphs from RCAEval traces (`has_traces`),
  and use them in the RP-18 guard.

## RP-27 (same day)

`sati.rca.cite.SatiRCAProvider` puts the ranker behind the Gateway. Its
citations are event ids, and the Reasoner's fabricated-citation check applies
to it unchanged; 3 tests cover this. The done-when waits on the 20 labelled
incidents (RP-13).

## Guard and RP-28 (same day)

- **Reference topologies moved to core.** The authored RCAEval graphs now
  live in `pashupatastra.kaal.references`, shared by the RP-18 guard and
  sim-to-real. 0 of 50k generated topologies match Online Boutique or Sock
  Shop, and the manifest was regenerated.
- **RP-28 Sati arm: not built, on purpose.** A PIB brief carries only three
  stack-level numbers, so there is nothing for RCA to rank. Extending
  `observe()` changes the benchmark contract and requires re-running every
  arm, which is the owner's decision. The plan records the proposal.

## RP-32 (same day)

The RCAEval subset was declared and committed before any full result: 490 OB
and SS cases at revision `afeacb1`, hash `55db1d9`. The adapter
(`sati.rca.external`) keeps the answer out of the inputs, and tests enforce
it. Sim-to-real now uses the pinned subset, and RP-33 is started.
