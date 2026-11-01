# Sati AI is native in the app

- **Date:** 2026-11-01
- **Phase:** Product (RP-96)
- **Commit(s):** pending

## What changed

The app's Sati AI tab is `AskScreen.kt`, a native chat posting to `/agent/ask` (with history, the last 6 turns, as the site sends). The full web console opens above it via `/ask?full=1`. `Api.post` runs on its own executor (`Api.CHAT`) so a slow answer never blocks Home or Incidents loads. `AppLock.kt` is the optional biometric or screen-lock lock with `FLAG_SECURE`.

## Why

The owner said Sati AI on the phone was too slow and looked bad. Twice the emulator killed the app while `/ask` was open (Play services' font provider died, apparently under memory pressure). A native chat removes the heavy page from the default path.

## Decisions made

- **Own models only** (see the owner's rule): the chat calls the API, which routes to the Sati models; there is no outside LLM.
- **Byline job first** (adr/Navadurga): "Sati · Technique match · Brahmacharini".
- **Answers render the API's light markdown natively:** bold, "- " bullets, and URLs plus CVE/CAPEC/T-ids linked like `lib/answerlinks.ts`. If the API's answer format changes, `AskScreen.format` must follow.

## Next session should

- Check that the emulator runs no longer report the Play-services kill on shot 5. If they still do, the cause is not the /ask page.
