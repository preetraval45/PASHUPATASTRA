# App phases: real incidents, native detail, updater, page review

- **Date:** 2026-11-02
- **Phase:** Product (RP-96)
- **Commit(s):** 4a27321, 9ffef45, 65bb8a1, 85c7f49, 689de5c, 8353171, acf337c, 8c93225

## What changed

- `IncidentsScreen`: a Live/Record tab pair. `kindOf(id)` and `KINDS` live in Api.kt, mirroring apps/web/lib/incidentkinds.ts. Add a new kind in four places: KINDS, the regex, `NativeScreen.kindLabel`, and the strings in en/hi/es (plus PAST_KINDS if the record serves it).
- **Native detail:** `openDetail(id)`. `NativeScreen.onBack()` and `title` let a native tab hold its own page. `MainActivity.open` routes `/incidents/(LIVE|PAST)-…` and `/ask?q=`.
- `Updater.kt`: DownloadManager into the app's external files dir (no permission needed); `Api.sideloaded()` hides it on Play copies (Play forbids self-update).
- `screens.sh` photographs every More page (p-*.png), and its "4-incident" shot is the first LIVE incident.

## Decisions made

- **The owner's "start phases and complete all pages" was read as:** phase 1, native incident detail; phase 2, review every page in CI and fix. Training stays web: its quizzes and progress sync live there.
- **The GitHub API rate limit (60/h unauthenticated) ran out from polling.** Poll every 2–3 minutes.

## Open questions

- Content seen in the page review, in the peer session's area: /detections leads with a drill, /search offers a scenario, /attack's matrix is empty for live incidents. Reported to pashupatastra-90.
