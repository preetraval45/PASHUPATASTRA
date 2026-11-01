# Android app gets a native frame

- **Date:** 2026-11-01
- **Phase:** Product (RP-96)
- **Commit(s):** pending

## What changed

The Android app now draws its own Material 3 frame: a top bar, a bottom tab bar with one WebView per tab, a "More" bottom sheet, and native loading and offline screens. The site hides its web header and tab bar only when the user agent carries `PashupatastraNative/1`.

## Why

The owner said the app "looks like a website saved as an app". The web-drawn bars (RP-83, RP-90) were the giveaway: they scrolled, reloaded and lagged like a page. A full native rewrite of every screen (chat, training, charts) would fork the product, so the frame and the navigation are native and the screens stay the live site.

## Decisions made

- **A separate `PashupatastraNative` UA token, not `data-app`:** `data-app` also marks iPhone home-screen installs and older APKs, which have no native bars. Hiding the web bars for them would strand them without navigation.
- **One WebView per tab:** that is what makes tabs feel native (state and scroll kept). Paths outside the four tabs open in a fifth "More" stack. Links followed inside a tab stay in that tab's history, as in native apps.
- **Theme:** the site's localStorage `theme` is the truth. The native switch writes it into every tab, and each page load syncs the bars from it.
- **Insets are handled at the root and consumed:** the bars pad themselves. The tab bar is GONE while the keyboard is up, and the root pads by the IME inset. With targetSdk 35 (forced edge to edge), `adjustResize` alone would not lift the Sati AI composer.
- `offline.html` and `AppBridge.retry` are gone; the offline screen is native, inside `WebTab`.

## Next session should

- Read the CI result of the first native build. Compile errors arrive as the annotation (see AndroidApp.md). Then tick RP-96 with the run ID.
- Store screenshots for RP-85 can now be taken from this frame.
