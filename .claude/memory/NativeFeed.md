# Android Live attacks feed, placeholders, badge

- **Date:** 2026-11-01
- **Phase:** Product (RP-96)
- **Commit(s):** pending

## What changed

`FeedScreen.kt` renders `/intel` groups natively, reached at `/observatory` through a synthetic tab id (`feed`) that marks More in the tab bar. `NativeScreen.skeleton` provides pulsing placeholder cards. `MainActivity.setNeedYou` puts a badge on the Incidents tab.

## Decisions made

- **A feed card opens the source's record, never the indicator:** the titles are defanged, and only `provenance.url` starting with https is linked (rule 1, provenance).
- **Native screens reached from More use synthetic ids (`View.generateViewId`),** mapped to the More nav item in `select`. Add more the same way: `rootPath`, `tabFor`, `hasNative`, `native`, and the title in `updateChrome`.
- The owner keeps asking for "more and better UI". The remaining web-only tabs (Sati AI, Training) stay web on purpose: they carry features a native copy would lose.
