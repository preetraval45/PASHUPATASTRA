# ExternalBenchmarkFeasibility

- **Date:** 2026-10-10
- **Phase:** Research plan, Block D — RP-31 (Claude's part)
- **Commit(s):** this push

## What changed

`docs/adr/ExternalBenchmark.md` (Proposed) compares RCAEval, OpenRCA,
AIOpsLab and ITBench on licence, size, form, labels, fit to Sati-RCA, and
whether each runs on free compute. It recommends RCAEval, starting with RE2.

## Why

RP-31 had no dependencies, and everything else Claude owns in Block A waits on
the owner (RP-06 needs RP-04 and RP-05). The owner wants only free compute, so
"runs on a GitHub runner, Kaggle or the Oracle box" became a criterion.

## Decisions made

- OpenRCA was marked down: no stated data licence, and it asks for ≥ 80 GB of
  disk and 32 GB of RAM, more than any free option provides.
- Only RCAEval's root-cause-service label matches what RCA@k scores.
- RE1 has metrics only, so the service graph has to come from the apps'
  manifests. RP-32 must record where each graph came from.
- The RCAEval topologies (Online Boutique, Sock Shop, Train Ticket) must go
  into the RP-18 contamination guard.

## Next session should

- Once the owner decides, fill in the Decision field and set the ADR to
  Accepted. RP-32 can then start.
