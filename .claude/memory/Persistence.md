# Persistence, contracts, and the brand mark

- **Date:** 2026-08-11
- **Phase:** Phase 0 — everything buildable without AWS access is now done
- **Commit(s):** pending

## What changed

Postgres landed: schema, migration runner, a store implementation, and 11 tests
that run against a real database rather than a mock. The OpenAPI document is
exported to `openapi.json` and CI fails when the public surface drifts from it.
Two ADRs closed the Phase 0 decision gaps — **Schema** (accepted) and **Graph**
(deliberately deferred, with criteria). The logo, lockup, and `docs/BRAND.md`
exist. The audit log now writes to Postgres when reachable and reports
`degraded` on `/health` when it cannot.

## Why

The interesting decisions were about *where* invariants live.

Three properties moved out of Python and into the schema, because a rule the
application enforces is a rule the next caller can forget:

- `audit_record` and `incident_transition` reject UPDATE and DELETE via trigger.
  An audit trail that can be retro-edited is not an audit trail.
- `execution.verdict_id` is NOT NULL, so a row describing an unauthorized action
  cannot be written even by something reaching SQL directly. This is the last
  line beneath `require_verdict`, not a duplicate of it.
- `verdict` has a CHECK that effective risk cannot fall below base risk, and
  `hypothesis` a CHECK that evidence is non-empty. Both mirror core validators;
  both exist because the core validator can be bypassed and the database cannot.

The migration runner records a checksum per applied file, so an applied
migration that later changes on disk is a hard error. Silent divergence between
environments is the failure mode that makes "migrations run clean" meaningless.

## Decisions made

- **Migrations ordered by a manifest, not by numbered filenames.** Keeps the
  repository naming convention (no numbers, dashes, underscores) without losing
  determinism. Applied lines are immutable.
- **The audit log degrades to memory but says so.** A hard failure would make
  local development require Postgres; a silent fallback would let production run
  without durable audit. `status: degraded` on `/health` is the middle path, and
  a test asserts the two can never disagree.
- **`openapi.json` is committed and CI-checked.** FastAPI generates the spec, so
  it cannot drift from the code — but it *can* drift from what consumers were
  promised. The committed file makes a surface change show up in review.
- **Graph store ADR deferred rather than decided.** Postgres is almost certainly
  right and is already the working default, but recording it as accepted would
  overstate the evidence. The ADR instead lists the five measurements Phase 1
  must produce. Writing a guess with the authority of a decision is worse than
  writing nothing.
- **The logo keeps the reference artwork's structure and palette, not its
  execution.** Trident head, shaft, star node, fletching, teal and gold — drawn
  geometrically. Teal is perception, gold is action; nothing is gold until it can
  act. An illustrated weapon reads as a game studio, which is the wrong signal
  for software asking for production credentials.

## Environment notes for the next session

- A **native PostgreSQL 17 Windows service owns port 5432** on this machine. The
  compose stack therefore publishes Postgres on **5433**, and every default URL
  points there. Do not "fix" this back to 5432.
- Docker Desktop must be running; the daemon is not started automatically.
- `aws` CLI and `terraform` are **not installed**.

## Open questions

- The API still reads incidents from the in-memory seeded store; only audit is
  durable. Wiring incidents and verdicts through `PostgresStore` is the next
  mechanical step — `save_incident` and `get_incident` already exist and are
  tested.
- No connection pooling yet. Every call opens a connection, which is fine at
  current volume and will not be at Phase 1 ingestion rates.
- `openapi.json` is committed but not linted for style (operation IDs, response
  models). Worth adding before external consumers exist.

## Blocked, and on what

Not engineering problems — they need credentials or a human decision:

- **AWS accounts, CloudTrail, budget alarms, Terraform state backend** — need an
  authenticated CLI profile. A console password cannot be used programmatically;
  `aws configure sso` is the path.
- **Vercel deployment** — needs a connected account and a public API URL.
- **Threat model review** — needs a second human reader.
- **Name clearance** — legal and commercial, and it gates all public activity.

## Next session should

Wire incidents and verdicts through `PostgresStore` so the in-memory store is
gone entirely, then start Phase 1 with the Prometheus connector — the topology
graph needs live input before any blast-radius number means anything.
