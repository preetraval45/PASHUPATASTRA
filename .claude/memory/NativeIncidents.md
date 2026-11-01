# Android Incidents tab is native

- **Date:** 2026-11-01
- **Phase:** Product (RP-96)
- **Commit(s):** see git log; green in CI run 41324018593

## What changed

`IncidentsScreen.kt` is the Incidents tab's first screen: filter chips and cards from `/incidents`. Shared drawing code moved to `NativeScreen.kt` (an abstract base with palette, cards, ripple and press) and API code to `Api.kt`.

## Decisions made

- **Native list, web detail:** the incident page (causal chain, plan, Dharma approval) stays on the site. Re-implementing approvals natively would duplicate the policy-facing UI, and rule 2 is easier to keep with one approval surface.
- **A detail page is a fresh WebTab above the list (`show` with a url on a native tab).** Opening a second incident drops the first page, so back always lands on the list. `closePage` removes the tab from `tabs` before its slide-out ends, so a quick re-tap cannot resurrect it.
- `/incidents?severity=x` from Home picks the native filter instead of loading the web page.

## Next session should

- A native Sati AI chat over `/agent/ask` (see `askGeneral` in apps/web/lib/api.ts for the request shape) is the next screen worth making native.
