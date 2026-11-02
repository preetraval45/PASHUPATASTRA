# Real incidents only (RP-108)

- **Date:** 2026-11-02
- **Phase:** Block I — live, published, on phones
- **Commit(s):** c7b21d6, 7404a12, this push

## What changed

`/incidents` lists LIVE-* incidents derived on read (10-min cache per process) from the feed events in the store (`app/feeds/liveincidents.py`); PAST-* incidents come from `app/history/history.json` (git-ignored, written at deploy by `scripts/fetchhistory.py`: full CISA KEV + HIBP breaches) via `/incidents/past`. Production sets PASHU_LIVE_INCIDENTS=true. Scenarios stay seeded and reachable by id; Blue Team drills read `STORE.exercises()`.

## Why

Owner: no demo data; big real dataset, live and past.

## Decisions made

- Derived, not stored: no stale copies, no Dynamo writes; an incident leaves when its window passes.
- Past starts where the live window ends, so nothing is listed twice.
- Ransomware victims are counted by sector/country, never named. Indicators defanged inside the incident.
- Feodo history: the aggressive blocklist is gone (404); ransomware.live terms unstated, so not bulk-ingested.

## Open questions

- Feed per-run limits (25) could rise; needs the DynamoDB billing mode (awsops status prints it).
- Overview/analytics still show scenario audit records.

## Next session should

- Move overview/analytics/observatory onto live data; add NVD critical history.
