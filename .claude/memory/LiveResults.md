# Live sim-to-real results (RP-19 done)

**Date:** 2026-10-27

## Why
The live-incidents run (40514270591) finished with 200 of 200 incidents. This records what it showed and the doubt that was checked before it was reported.

## Decisions
- Headline: Katyayani trained on RCAEval scores 0.895, loudest 0.870, Kaal-trained 0.335, earliest 0.250, chance 0.125. It is in PAPER §7.2, the Katyayani card and the plan.
- The doubt: at 2σ every service is "anomalous" in every incident. The live baselines are flat (median non-root peak 18σ, root 2,711σ). This is measured in a generated `katyayani-live-signal.md` (sati.rca.livesignal, from the dataset only) rather than asserted. It is stated as *consistent with* the Kaal collapse, not proven.
- `deploy_before` identifies the release fault. This is an L2-style exposure, noted in the RP-12 notes.

## Next session
- To make the realism count meaningful, a noisier live load (variable RPS, jitter) is needed. That means changing the app/plan, which reruns the set.
- Use fewer shards (e.g. 10): 20 shards held every runner for an hour and queued CI and deploys.
