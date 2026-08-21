# The chat panel, and a verification that lied twice

- **Date:** 2026-08-21
- **Phase:** Phase 3 — R21
- **Commit(s):** pending

## What changed

Sati is visible. A collapsible panel on the incident page, four starter chips,
every citation a link. `scripts/verifychat.py` drives it in a real browser:
four distinct answers carrying 4, 13, 1 and 9 citations, all resolving, none
dropped, all grounded. 18/18 layout checks still pass.

## Decisions made

- **Under the incident, not beside it.** A right-hand rail is the conventional
  shape and wrong here: at 375px it becomes a bottom sheet covering the thing
  being asked about, and the questions are *about* what the reader just read.
- **Collapsed by default.** An assistant that opens itself is something to
  dismiss before reading the incident.
- **A second link resolver, `hrefFor`.** The existing `Evidence` component sends
  everything to `/evidence/`, right only for event ids. A causal step or audit
  record sent there 404s — and a citation leading to "not found" is worse than
  one plainly unlinked, because it looks checkable and then fails.
- **Audit refs are keyed by timestamp, not position.** `audit#2` indexed a
  newest-first list, and answering a question *appends* an audit record, so by
  render time index 0 was the chat turn that produced the citation.
- **The loading indicator is motion, not a picture.** The owner asked for an
  arrow firing from a bow; the brand rule keeps illustrated weaponry to the logo.
  An arc that tensions and a streak that leaves it reads as the gesture without
  drawing the object — and a literal bow in a console would read as clip art.

## The verification lied twice, which is the part to remember

1. It located turns by counting `<p>` elements and read the visitor's own
   question back as the reply. Four green ticks, nothing tested.
2. Fixed, it fired the four questions back to back, hit the per-minute token
   allowance, and reported **one answer four times** — every other check still
   passing.

It now finds turns by `data-turn` attributes, paces itself under the allowance,
and **fails on identical answers**. A checker that can pass while the thing it
checks is broken is worse than no checker, because it is trusted.

## Local-only gotchas

- `next start` on this machine 400s the `[id]` client chunk (OneDrive +
  bracketed paths), so nothing hydrates and the panel looks dead. `next dev`
  works. Not a defect in the app — but it will waste an hour if forgotten.
- The API's CORS allows `localhost:3000` only, so local verification must use
  port 3000. Any other port fails as "Could not reach the API", which reads like
  an outage and is the policy working.

## Open questions

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**
- Oracle box still not provisioned; a rate limit is a 429, not a slower answer.

## Next session should

- **R22** — model id, prompt version and the full tool-call trace into the audit
  table for every turn. The trace already exists on the response; it is not yet
  written where `/audit` can show it.
