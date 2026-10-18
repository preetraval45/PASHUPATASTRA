# OneSiteAnalyticsTraining

- **Date:** 2026-10-18
- **Phase:** Block G — RP-52 (partial), RP-54, RP-55, RP-56
- **Commit(s):** this push

## What changed

- One frame for every page. `(site)/layout.tsx` now renders `ConsoleFrame`
  too, and the sidebar gained Start, Analyze and Learn sections plus footer
  links to Impact and Press. nav.tsx is deleted.
- The Ask page is renamed "Sati AI". The rail shows a sub-label, "investigation
  agent", to satisfy BRAND.md's first-mention rule.
- New `/analytics`, with charts from components/analytics.tsx (TimeBars,
  Breakdown, DayColumns): hand-drawn, real data only, interactive.
- New `/training`, a drill hub over the game scenarios with per-browser
  progress. `/blue-team` redirects to it.

## Why

The owner said the console and the site looked like two products, and that
there was no analytics page and no cybersecurity training page.

## Decisions made

- The production API is weeks behind main. `/usage`, `/figures`, `/impact`,
  `/attack/matrix`, `/detections` and `/models` all return 404 there. Analytics
  names a missing source instead of drawing an empty chart.
- The audit history spans only about an hour, because the memory-only store
  resets on cold start. TimeBars therefore picks its bucket size from the span
  of the data.
- The owner reversed model ownership: Claude now builds and trains all Sati
  models, on RCAEval, CIC-IDS2017/UNSW-NB15, LogHub and NAB/SMD, using free
  cloud compute. "All AI should be my own AI": LLMs stay only as baseline and
  labelled backup.

## Next session should

- Add an API deploy workflow on GitHub Actions. It needs the owner's AWS keys
  as repo secrets. The deploy script replaces the Lambda environment block, so
  the workflow must preserve the model settings.
- The real-data ML pipeline, starting with Sati-RCA on RCAEval.
