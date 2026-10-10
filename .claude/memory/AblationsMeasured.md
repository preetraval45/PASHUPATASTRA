# AblationsMeasured

- **Date:** 2026-10-10
- **Phase:** Research plan, Block A — RP-01 closed
- **Commit(s):** cfc3d12 (tables, by the workflow), this push (plan tick)

## What changed

Table 2 has data: −no-policy and −no-verification at N = 3, n = 93 each, from
GitHub Actions run 38073266499. RP-01 ticked; backlog 5.4 "run and recorded"
removed.

## Why

RP-01's done-when line — Table 2 n > 0 for both rows — is now true, and the
result was cross-checked: a local −no-policy run on a different machine gave
the identical 78/93.

## Decisions made

- Reported −no-policy as "no effect on this corpus", not "policy does not
  matter": the deterministic proposer never proposes anything Dharma blocks, so
  the 31 executable scenarios cannot exercise the policy layer. That is a corpus
  gap, and the LLM proposer arms (RP-06/07) are what will exercise it.
- −no-verification lowers HIR by exactly the 5 remediate scenarios while Correct
  is unchanged. Recorded as a *likely* reading (failed remediations stop
  reaching a human) — confirm from the per-scenario records in the
  `pib-records` artifact before the paper states it.

## Open questions

- Should the grader count "failed remediation hidden from humans" against an
  arm? Today −no-verification scores the same Correct as the full architecture.
  That is a metric-design decision for the owner.

## Next session should

- RP-03 (related-work log, Claude part) and RP-04 (Sati models ADR draft) need
  nothing external. RP-06/07 need the owner's model decisions.
