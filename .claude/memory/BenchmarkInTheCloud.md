# BenchmarkInTheCloud

- **Date:** 2026-10-10
- **Phase:** Research plan, Block A — RP-01
- **Commit(s):** pending

## What changed

`.github/workflows/benchmark.yml` runs PIB on GitHub's runners: four parallel
jobs (full architecture, −no-policy, −no-verification, runbook), each with its
own kind cluster, N = 3. A final job merges the records, keeps them as the
`pib-records` artifact, regenerates `docs/research/tables.md` and commits it.
Triggered by `workflow_dispatch` or a push that changes the workflow file.

## Why

The owner does not want anything running on their PC, or depending on it being
on, and wants only free services. AWS free tier has no GPU and no credentials
were on the machine; the Oracle box needs SSH access not yet given. The repo is
public, so Actions minutes are free and need no new account or secret.

A local attempt on 9 October got the −no-policy run done (93 records, local
only) before the session ended mid −no-verification. It was abandoned rather
than resumed, because the owner objected to it running locally.

## Decisions made

- All four variants rerun together — the full-architecture and runbook records
  behind the published Table 1 were never committed and were not on this
  machine, so regenerating the tables without them would have blanked Table 1.
  Same runner type for every row keeps the comparison fair.
- Records stay gitignored, as before; they live as an artifact (90-day
  retention). Only the generated tables are committed.

## Open questions

- Should run records become committed artifacts so a third party can recompute
  Table 1/2 after the artifact expires? That reverses the existing gitignore
  policy, so it is the owner's call.
- Longer term: the Oracle Always Free box (always on, 24 GB) for serving and
  LLM baselines, Kaggle for GPU training. Both need the owner's access first.

## Next session should

- Read the regenerated tables, report the ablation deltas and any UNSTABLE
  scenario, and tick RP-01 plus the backlog 5.4 line if Table 2 has n > 0 for
  both rows.
