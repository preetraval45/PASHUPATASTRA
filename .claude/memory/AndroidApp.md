# Android app: the live site in a native shell

- **Date:** 2026-10-29
- **Phase:** Product (RP-82, RP-83; RP-85 and RP-86 next)
- **Commit(s):** 36e9dc0, f36e97f, 1d30a61, c0734e2

## What changed

- `apps/android` is a Kotlin WebView app around pashupatastra.vercel.app. It has pull to refresh, back navigation, an offline page, a share sheet, and a splash screen with the launcher icon from `scripts/buildbrand.py`.
- `.github/workflows/android.yml` builds the APK in CI and republishes the `android` release. The home page links that APK, except inside the app, which it detects by `PashupatastraApp` in the user agent.
- Phones get a bottom tab bar.

## Why

- **Owner's choice (29 Oct):** the free sideloaded test app now. The Play Store ($25 once, a 12-tester/14-day closed test for new personal accounts) and iOS ($99 a year; guideline 4.2 rejects plain wrappers) come later.
- **A WebView, not a TWA:** a TWA needs Digital Asset Links. For the store build, revisit whether to switch.

## Decisions made

- **Test signing key:** it is committed and public (`apps/android/test-signing.jks`, password `android`), so every CI build installs over the last. It must never sign a store build; RP-85 uses a private key held as a GitHub secret.
- **Pull to refresh:** the site scrolls inside a panel, not the window, so the page reports whether it is at the top through `AppBridge.atTop`. Without that, pull to refresh would fire mid-page.
- **Reading CI build errors without `gh` auth:** the workflow posts Gradle's "What went wrong" as an annotation. Read it with `/check-runs/<job>/annotations`.

## Next session should

- Make the store listing assets: screenshots and a privacy page.
- Make iOS native features (push, Face ID approvals) before an App Store submission.
