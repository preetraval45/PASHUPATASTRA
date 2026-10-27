# Live sim-to-real set (RP-19)

**Date:** 2026-10-27

## Why
RP-19 asked for ~200 fault-injected incidents from "the real cluster". The PIB stack is pause containers, which report replica counts only. Katyayani needs service metrics, so a PIB-based set would have measured nothing.

## Decisions
- A new eight-service stack (`benchmark/live`). It is stdlib Python from a ConfigMap on `python:3.12-slim`, so nothing is built. A loadgen and an in-cluster collector write RCAEval's layout, so `sati.rca.features` is reused unchanged.
- The four faults are none of PIB's types: cpu, mem, delay and release. Injection is from outside (kubectl exec / set env). Release creates a real ReplicaSet, which gives an observable deploy_before.
- The plan is pre-declared and hash-locked. Errors stay in the dataset (assemble.py), so a failure cannot shrink the denominator.
- The live graph is not added to `kaal.references.REFERENCES`: that would change the Kaal manifest. Instead, a test checks that the live shape differs from OB, SS, PIB and 2,000 Kaal graphs.

## Next session
- Collect the `live-incidents.yml` run. It commits `benchmark/live/dataset` and `models/katyayani-live.md`.
- Then tick RP-19, and update RP-18 step 3 (realism versus real is now in that report), the paper §7.2, and the Katyayani card.
- If shards fail, check whether `kubectl exec deploy/...` and cgroup v2 work in kind pods (`metric_source` in the results says which source was used).
