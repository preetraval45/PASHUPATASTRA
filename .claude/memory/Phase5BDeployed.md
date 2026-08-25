# A link can be lost without anything overflowing

- **Date:** 2026-08-25
- **Phase:** Phase 5B — Satisfying to operate (R67, closing R60–R66)
- **Commit(s):** pending

## What changed

Phase 5B is deployed: Lambda rebuilt and updated (carries `tier_reasons`,
reports `ok · dynamodb`, model key preserved), Vercel aliased to
`pashupatastra.vercel.app`. A **Home** tab was added to the nav at the owner's
request during the phase, which is what surfaced the finding below. Three
checkers were strengthened: `verifyui.py` hit-tests header items and checks two
more viewports, `verifychain.py` samples at phone width, `verifylive.py` tells a
real feed sync from a page deriving its age from load.

## Why

R67's clause is that the palette, the chain reveal and the blast-radius graph
each work on a phone *or are absent by design rather than by accident*. Two of
the three were already measured there. The chain reveal was not — it had only
ever been sampled at 1280x1000, the width it was designed at.

## Decisions made

- **`verifyui.py` hit-tests at three points per header item, not one.** The
  seventh nav label sat underneath the search field at 1024px with nothing
  overflowing, so every check passed. A centre-only test then accepted a
  breakpoint where the field overlapped the last label by 7px. Rules out the
  class of bug where an element is the right size, in the right place, and
  covered.
- **The nav row's breakpoint is a measured custom screen (`nav: 1160px`), not
  `lg` or `xl`.** Gap to the search box: -7px at 1100, +5px at 1120, +38px at
  1160. `xl` would have handed every 1024–1280 laptop a hamburger it has room
  not to need.
- **Both sides of a breakpoint are checked.** The viewport list had nothing at
  1024, the width the row turns on at — the one width whose entire purpose is to
  switch behaviour.
- **`verifychat.py` does not skip on the rate-limit message.** A checker that
  passes when the page says a particular sentence is a checker the page can
  switch off.
- **R94 marked `[~]` rather than left ticked.** Its checker fails on the
  deployed agent, on its own worked example.

## Open questions

- **R94: Sati declines the `ws-0148` SMB question at hop 0 with no tool call**,
  twice in a row, while other questions in the same battery do call tools. Was
  it a prompt regression, model drift on a free non-deterministic tier, or a
  question the tools cannot start on? Declining *after looking* is correct; no
  tool call is not looking.
- The free model allowance is per-minute and `verifyagent`/`verifychat` both
  trip it. Neither can currently distinguish a rate limit from a defect.
- `npm run build` while `next dev` is running clobbers the shared `.next` and
  produces phantom failures across every checker. The repo also lives under
  OneDrive, which locks `.next` (EBUSY) after a killed dev server; `rm -rf
  apps/web/.next` and restart.
- `openapi.json` staleness from R65 is still worth confirming against CI.

## Next session should

- Phase 5C (R68–R73), Sati deeper — or R94 first, since R95 depends on it and it
  is now known-broken on the deployment.
