# Durable state on DynamoDB

- **Date:** 2026-08-21
- **Phase:** Phase 2 — R18
- **Commit(s):** pending

## What changed

State survives a cold start. `DynamoStore` persists incidents, the audit trail,
events and topology into one table, `backend.durable()` decides once per process
which store is in play, and `/api/v1/health` names whichever one answered rather
than asserting a backend. `_seed_demo` became idempotent against a version
marker. Verified live: a verdict took the trail 30 → 31, every container was
forcibly replaced, and the new one still reported `ok · dynamodb · 31 records`.

## Why

R19's chat needs memory between turns, and a store that empties on every cold
start is not memory. DynamoDB over RDS because its free allowance does not
expire; provisioned 25R/25W because on-demand has no perpetual free tier.

## Decisions made

- **One resolver, `backend.durable()`** — incidents, the audit trail and the
  graph each used to decide durability for themselves. They could disagree, and
  then `/health` is answering for a third of the system.
- **A sequence in the audit sort key** — two records written in the same
  millisecond otherwise overwrite each other. An audit trail that drops a record
  under load is not an audit trail.
- **`dynamo_namespace`, prefixed onto every partition key** — one table holds
  `prod` and `test` without either seeing the other. A second table was not an
  option: the free allowance is per *account*, so it would have split
  production's headroom rather than added any.
- **The namespace guard lives in `services/api/tests/conftest.py`** — importing
  `app.main` runs the seed as an import side effect, so the guard has to be set
  before any test module loads. Asserting it inside each test is too late.
- **DynamoDB answers graph questions itself** (`answers_graph = True`), where
  Postgres is routed through `GraphStore`'s SQL. Getting this wrong sent the
  Dynamo store into `connect()` looking for a Postgres connection.
- **Traversal is still `TopologyGraph`'s** — hydrated from the table, not
  reimplemented. A fourth blast radius is a fourth answer to a question risk
  scoring depends on.

## What this cost, and the lesson

Durability changes what a mistake costs. Twice in this phase something was
written that in memory would have vanished at the next restart and in a table
simply stayed: a local run seeded the *infrastructure* incident into the
security console, and this phase's own tests put four fixture hosts on the live
service map. Both were invisible until the live site was read back. **Check the
deployed data after a change makes it durable** — the tests passed throughout.

## Open questions

- Still unanswered after five askings: is `logo.png` or the square spear the
  Google Search icon?

## Closing state

The table was emptied of everything written before namespacing — the stray
incident, the test fixtures, the legacy un-namespaced rows — and the console
re-seeded itself under `prod`. Live: `ok · dynamodb · 3 incidents`, 11 topology
nodes, and a record written before a forced container replacement still there
after it, with the count holding at 3 rather than doubling. 18/18 UI checks pass.

`scripts/cleardynamo.py` is the maintenance tool; it deletes nothing without
`--yes`. Note for future sessions: the permission classifier blocks bulk deletes
and chained commands, so run them one namespace at a time and expect to ask.

## Next session should

- R19 — the chat route. Needs the paid Anthropic API, which has no free tier.
