# Android incident alerts, and a split-refactor slip

- **Date:** 2026-11-01
- **Phase:** Product (RP-96)
- **Commit(s):** pending

## What changed

`IncidentWatch.kt` is a WorkManager worker that polls `/incidents` every 15 minutes. It notifies once per new (id, state, severity) that awaits approval or is open and critical; tapping a notification opens the incident. There is an on/off switch in the More sheet. This push also fixes the previous push's build: moving code out of HomeScreen left a stray `}` at the end of `Api.kt`.

## Why

Push notifications through FCM need a Firebase project (an owner account). Polling the public API needs nothing, sends nothing from the phone, and is enough for incidents that change on a scale of minutes.

## Decisions made

- **The first run only records a baseline,** so enabling alerts never floods the phone with every existing incident.
- **Permission is asked once,** 1.5 s after first launch (Android 13+). If it is denied, alerts are switched off rather than silently doing nothing.
- **`schedule`, not `apply`:** naming the companion function `apply` shadowed Kotlin's scope function inside the companion.

## Next session should

- After Kotlin edits made by moving or splitting code, count braces per file before pushing. CI is the only compiler, and each failed round costs a run.
