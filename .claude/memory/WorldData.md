# WorldData

- **Date:** 2026-10-18
- **Phase:** Block G — RP-70
- **Commit(s):** this push

## What changed

scripts/worldsnapshot.py (stdlib only) fetches CISA KEV, ransomware.live
v2/recentvictims, the Feodo ipblocklist and HIBP breaches, then writes the
aggregates to apps/web/lib/world.generated.json. world-data.yml runs it every
day at 06:17 UTC, on dispatch, and on changes to the script. /world renders the
result, and the rail links to it as "World threats" under Analyze.

## Why

The owner wanted world-scale data, not 3 demo incidents. The API's own feed
collectors can't run in production until AWS is deployed. This gets real
global data on the site now, through CI.

## Decisions made

- No victim names and no raw indicators, only aggregates. Victim names are
  published by criminals as leverage.
- This is static data committed by CI, the same pattern as
  evaluation.generated.json. It is not a data plane on Vercel.
- When AWS is live, the API feeds remain the system of record. /world is the
  public aggregate view.
