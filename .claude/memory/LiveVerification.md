# Live verification of the product tasks

- **Date:** 2026-10-26
- **Phase:** Block G — Product UI
- **Commit(s):** pending

## What changed

RP-50, 51, 52, 66, 67, 68, 69 and 70 are ticked. Each one was waiting only on
the API deploy or a live check.

## Why

The plan allows `[x]` only with evidence. The evidence here was gathered on
26 Oct:

- Every API route the site uses answers 200 with data.
- Each page renders its expected content. This was checked by matching text
  in the served HTML, not only the status code.
- The world-data workflow has committed 8 snapshots.

## Decisions made

- `/api/v1/world` returns 404, and that is correct: `/world` reads the
  committed snapshot `apps/web/lib/world.generated.json`, not the API.

## Next session should

- The remaining partial product task is RP-57, which needs the owner's AWS
  secrets in GitHub.
