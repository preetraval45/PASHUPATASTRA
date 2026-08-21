# Real threat intelligence, on a schedule

- **Date:** 2026-08-21
- **Phase:** Phase 4 — R24
- **Commit(s):** pending

## What changed

CISA KEV and abuse.ch URLhaus are polled hourly by EventBridge Scheduler into
the Lambda, normalised into the event schema, and stored in DynamoDB with a
cursor. `/api/v1/intel` and `/api/v1/intel/status` read them back.

Proved by watching the schedule fire rather than by reading its configuration:
tightened to `rate(5 minutes)`, it invoked the function at 17:21:13Z on its own,
then was restored to hourly. **"Created" and "fires" are different claims.**

## Decisions made

- **`Verification` is a closed, ordered vocabulary.** CISA is `confirmed` — its
  entry criterion is evidence of exploitation. URLhaus is `reported`, always;
  those are community submissions the publisher does not assert. Rating an
  unreviewed submission as highly as observed exploitation is the mistake the
  type exists to prevent.
- **Intelligence is never a topology node.** `VULNERABILITY` and `INDICATOR`
  describe the world, not this estate, so they are referenced by events and
  never upserted. A map drawing a thousand CVEs beside eleven hosts says they
  are the same kind of fact, and blast radius would traverse from a host into a
  vulnerability. A test asserts the node count does not move on ingest.
- **The malware URL is never rendered.** Entries are keyed by host; the link is
  the advisory *about* the URL. A console rendering live distribution points as
  anchors is one that eventually gets clicked.
- **Polling is not an HTTP route.** An endpoint that fetches from third parties
  and writes to the store is one anybody can aim at, and protecting it would
  mean a second auth scheme for the one caller that is not a person. EventBridge
  invoking the function directly needs no secret — reaching it requires IAM.
- **The cursor advances after the write.** Advancing first means a failed write
  skips those entries forever and the gap is invisible: the feed looks quiet
  rather than broken.
- **One feed down does not stop the others.** A run aborting on the first would
  turn somebody else's outage into a gap in ours.
- **ThreatFox left out.** abuse.ch now requires an API key, and a key nobody has
  is a dependency that fails in production and passes in every test written
  around it.

## What this found

`recent_events` returned rows exactly as stored, publishing the table's own
`PK`/`GSI1PK` — including the namespace — and leaving payload, provenance and
labels as JSON strings for callers to parse. There was already a `_event_row`
normaliser that every other read used; I had bypassed it. A test now covers
every read path that returns events.

## The IAM grant

The deploying user could not create schedules. `PashupatastraPlatform` gained
`scheduler:*` scoped to `schedule/default/pashupatastra-*`, and `iam:PassRole`
on the scheduler role alone, conditioned on
`iam:PassedToService = scheduler.amazonaws.com`. **A `PassRole` without that
condition lets the role be handed to any service that will take it** — which is
how a scoped `PassRole` turns out not to be scoped.

## Open questions

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**
- Oracle box still unprovisioned; a model rate limit is a 429, not a slower
  answer.

## Next session should

- **R25** — the Observatory page. The data is already in the store and readable
  at `/api/v1/intel`; this renders it, with verification badges that never
  label a report as confirmed.
