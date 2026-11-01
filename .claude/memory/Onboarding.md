# Android first-run welcome

- **Date:** 2026-11-01
- **Phase:** Product (RP-96)
- **Commit(s):** pending

## What changed

`Onboarding.kt` shows three screens on first launch (pref `onboarded`) over `android.R.id.content`. The last one offers alerts: "Turn on alerts" asks for permission, "Not now" turns them off. It replaces the bare permission prompt that appeared 1.5 s after launch.

## Decisions made

- **The copy follows BRAND.md:** the first mention of Sati says what it is, and there is no imagery or mythology. The claims are ones the product keeps ("can propose but never act", "nothing is sent from it").
- **Insets:** the overlay is a sibling of the root, which consumes insets. Before API 30 siblings never see consumed insets, so it also reads `getRootWindowInsets` directly.
- **Skip on an early screen leaves alerts on** (the default, with permission asked); "Not now" on the last screen turns them off.
