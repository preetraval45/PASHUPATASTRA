# Demo deployment — Vercel + Lambda, no data layer

- **Date:** 2026-08-19
- **Phase:** Phase 0 — Foundation (0.8 Dashboard, 0.8.1 Demo deployment)
- **Commit(s):** pending

## What changed

The dashboard is live at `https://pashupatastra.vercel.app` and the API is
deployed to a Lambda function, `pashupatastra-api` in `us-east-1`. The API runs
with no Postgres at all: `GraphStore` and the entity/event reads now fall back to
an in-memory mirror when no database is reachable, the same seam `Store` already
had for incidents. `app/seed.py` replays the labelled corpus in
`benchmark/incidents/` into that graph at startup so the pages render something
true rather than empty states.

The two are not yet connected. AWS refuses anonymous invocation of the Lambda
Function URL, so the dashboard still shows its "API unreachable" state.

## Why

The ask was a public site someone could look at. Every page begins
`if (!health) return <Offline />`, so shipping only the frontend would have
produced a public URL that demonstrates nothing. Making the API serve without a
database was the cheapest honest way to fix that — cheaper than RDS, and it
keeps the deployment inside the always-free tier rather than the twelve-month
one.

## Decisions made

- **In-memory fallback delegates to `TopologyGraph` in packages/core** for blast
  radius and adjacency, and only adds the projections Postgres does in SQL
  (severity rollup, snapshot, entity events). Rules out a third implementation
  of a traversal that risk scoring depends on. `testgraphmemory.py` asserts
  agreement with the reference, mirroring what `testgraph.py` does for Postgres.
- **The seed invents nothing.** No dependencies beyond the two the demo incident
  already asserts, no user counts, and every event keeps
  `source_system="scenario"` in its provenance. Rules out a demo that looks
  richer by fabricating structure behind blast radius — which is a risk input.
- **`psycopg` is imported inside `db.connect`, not at module scope.** A
  deployment with no database does not carry the driver; it was a third of the
  archive. Also makes `packages/core`'s "must run on a laptop" claim true of the
  API in practice, not just in principle.
- **Build dependencies are read from the three pyprojects**, not listed in the
  build script. The first attempt hardcoded them, omitted `ulid-py`, and failed
  at runtime on the first request rather than at build time.
- **Lambda zip, not a container.** No ECR, so no registry storage cost.
- **CORS wildcards are rejected by the deploy script.** DEPLOYMENT.md says a
  wildcard is never acceptable, and the demo tier is the deployment most likely
  to be copied as a starting point.

## Open questions

- **Why does the account refuse anonymous Function URL invocation?** The
  resource policy is correct, `AuthType` is `NONE`, and a SigV4 request to the
  same URL returns 200 while an unsigned one gets 403 from AWS before reaching
  the function. There is no Lambda API for a public-access block in boto3
  1.43.74, so this is not an API-managed setting. Unresolved.
- Whether the demo tier should keep running once a real environment exists, or
  be torn down so `degraded` is never mistaken for the product.

## Next session should

- Run `python scripts/deployapigateway.py --cors https://pashupatastra.vercel.app`
  once the deploying IAM user has `AmazonAPIGatewayAdministrator`, then set
  `NEXT_PUBLIC_API_URL` on Vercel to the returned origin plus `/api/v1` and
  redeploy the dashboard.
- Re-run `scripts/deploylambda.py` with the same `--cors` so the app-level
  origin list matches the gateway's.
