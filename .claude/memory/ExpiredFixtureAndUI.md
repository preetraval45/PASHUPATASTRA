# ExpiredFixtureAndUI

- **Date:** 2026-10-18
- **Phase:** Research plan — Block G (Product UI) added; RP-46 and RP-47
- **Commit(s):** this push

## What changed

- The `core` CI job was red, which skipped `deploy site`. The cause was a test
  fixture in testreasoning.py: a Smriti memory dated against a fixed T0
  (17 Aug), while `recall` applies the 90-day retention against the real clock.
  It expired on 16 Oct. The fixture is now relative to now.
- On the Ask page, the incident `<select>` opened white with near-white text.
  Added `color-scheme` per theme and explicit `option` colours, and replaced
  the undefined `--bg` token used by three inputs.
- Plan: added Block G (RP-46…RP-53), the product-UI redesign the owner asked
  for. The owner wants the site to be the demo for their O-1A evidence.

## Why

The owner asked why nothing was deploying. Vercel's Git integration was
deploying every push the whole time (commit statuses say "Deployment has
completed"). The CI `deploy site` job is a fallback that only runs when
Vercel secrets are set, and it is skipped whenever any test job fails.

## Decisions made

- Fixed the test, not `smriti.py`. Retention against the wall clock is
  correct behaviour in production; only the test was date-dependent.
- RP-47 is `[~]` until it is confirmed on the deployed site.
- The redesign happens on a branch with Vercel previews. Main deploys
  production.

## Open questions

- Other tests may pin fixed dates against wall-clock logic. testcore.py uses
  `datetime.now()`, which is fine. A sweep for `T0`-style fixtures crossing a
  retention window would catch the next one.

## Next session should

- Build RP-48 to RP-53 on a `ui-redesign` branch, and send the owner the
  Vercel preview URL.
