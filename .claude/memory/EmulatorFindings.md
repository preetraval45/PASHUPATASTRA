# What the emulator run found, and offline copies

- **Date:** 2026-11-01
- **Phase:** Product (RP-96, RP-85)
- **Commit(s):** 3d608d3, a4f4aef, af2e34d, 5e357ec

## What changed

- The first emulator run showed the app vanish (launcher in `shot-4-incident.png`) when opening an incident page, with no Java crash. `WebTab` now handles `onRenderProcessGone` by rebuilding the WebView and reloading. Sub-frame and `about:`/`blob:`/`data:` navigations stay in the page. Later runs reach all eight screens with the app alive.
- `Api.fetch` keeps each answer in prefs (`api-cache`). The native screens paint from it on a cold start and show it offline, labelled "as of <time>". `/health` is never shown from a copy.
- CI: `concurrency: android-release` (two runs raced to recreate the release); `screens.sh` has no `set -e`, writes `summary.txt` (running / NOT RUNNING per screen) and gives its verdict last. Only non-empty files are uploaded, because GitHub rejects an empty `crash.log`.
- Page `<h1 data-page-title>` is hidden under `html[data-native]`; TalkBack descriptions on the native cards; `enableOnBackInvokedCallback`.

## Decisions made

- **Evidence lives on the public `android` release** (`shot-*.png`, `summary.txt`, `logcat.txt`) because `gh` is not authenticated here and job logs need auth. Read them with curl.
- **Diagnose by device state, not by crash buffer:** a renderer death leaves no Java crash, so `summary.txt` checks `pidof` after every screen.

## Next session should

- Read `summary.txt` and the shots after every Android change; they are the only eyes on the app.
