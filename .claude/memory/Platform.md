# Platform and build

- **Date:** 2026-08-10
- **Phase:** Phase 0 → early Phase 3 (the policy layer landed ahead of schedule)
- **Commit(s):** `496960f`

## What changed

AWS became the target platform, Vercel the dashboard host, and the repository
stopped being docs-only. `packages/core` now holds a working domain model —
events, incidents, Dharma policy, agents, topology, and the closed action
registry — with 20 passing tests. `services/api` exposes it over FastAPI with 14
passing tests centred on the rule that matters: no execution path reaches a
connector without a policy verdict. `apps/web` is a Next.js dashboard rendering
the demo incident, its causal chain with evidence citations, and the action
registry. Docker-compose, a Terraform skeleton, and CI complete the loop.

All files were also renamed to drop numbers, dashes, and underscores at the
user's request — docs use spaced names (`Incident Model.md`), ADRs and memory
entries use topic names, and ordering moved into the index files.

## Why

The build order was deliberate: Dharma before Astra. If the action engine had
been written first and policy retrofitted, the verdict argument would have been
optional in practice, and every later execution path would have been a place to
forget it. Writing `execute()` so it *cannot* be called without a verdict makes
the Phase 3 exit criterion a type-level property rather than a review checklist
item.

AWS was chosen for managed durability — the audit trail surviving an AZ loss is
a correctness requirement, not a convenience — and because IAM gives a second,
independent enforcement layer beneath Dharma. CloudTrail additionally provides an
out-of-band record to check the system's account of its own actions against,
which is rare and worth publishing.

## Decisions made

- **AWS target, but `packages/core` stays cloud-free** (ADR Platform). Enforced
  in CI by a grep that fails the build on any `boto3` import in core. Rules out
  AWS types in the domain model permanently; keeps the on-prem wedge open.
- **Vercel hosts the dashboard, AWS hosts everything with authority.** Safe only
  because the dashboard computes nothing — it renders API answers. It never
  receives AWS credentials; `NEXT_PUBLIC_*` is world-readable by definition.
- **Every AWS service choice has a working self-hosted counterpart**, and CI runs
  the benchmark against the compose stack, so a broken on-prem path fails the
  build instead of surfacing at the first enterprise deal.
- **No long-lived IAM keys anywhere** — SSO+MFA for humans, IRSA for workloads,
  GitHub OIDC for CI. Added as threat T9.
- **`delete_infrastructure` is registered specifically so it can be denied.** IAM
  grants it to no role, so registering it adds a policy record without capability.
- **Missing telemetry grades verification as failure, not success.** "Don't know"
  must never be recorded as a pass.
- **Filenames carry no numbers, dashes, or underscores.** Python module and test
  files are the exception — `__init__.py` is mandatory and pytest discovery needs
  a `test` prefix, so those stay compact (`testdharma.py`).

## Open questions

- The user declined to rotate an IAM console password that was pasted into the
  session. It remains exposed in the transcript and terminal scrollback. Not
  actionable from here, and not raised again — but if unexplained CloudTrail
  sign-in events ever appear, this is the first thing to check.
- `aws` CLI and `terraform` are not installed on this machine, so nothing has
  been applied to a real account. Terraform is providers and variables only.
- Store is in-memory. Phase 0.5 moves incidents, verdicts, and audit to Postgres;
  the audit log's append-only contract is the part that must not drift.
- Bedrock model availability by region vs. where customer telemetry may legally
  reside — unresolved, and it constrains which regions can serve which customers.

## Next session should

Wire the Postgres schema behind `services/api/app/store.py` — it was written
behind a single seam specifically so this swap touches one file. Then the first
real connector (Prometheus), since the topology graph needs live input before the
blast-radius numbers mean anything.
