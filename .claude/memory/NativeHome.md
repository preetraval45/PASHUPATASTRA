# Android Home tab is native

- **Date:** 2026-11-01
- **Phase:** Product (RP-96)
- **Commit(s):** pending

## What changed

The Home tab is now drawn by `HomeScreen.kt` from the public API (`BuildConfig.API_URL`, the API Gateway URL, overridable with `-PapiUrl`) instead of loading `/` in a WebView. The other tabs are still pages.

## Why

The owner wants the app to differ from the website, not just be framed by it. Home is the first screen and needs only two public JSON endpoints, so it was the cheapest screen to make truly native. No new dependencies: HttpURLConnection, org.json and a single-thread executor.

## Decisions made

- **Rule 1 holds on a phone too:** the counts read "–" until the API answers, and an unreachable API is said, never papered over.
- `MainActivity.show` tracks `shown` (a View), since Home is not a WebTab. `current` is null on Home.
- **Owner asked for Claude/GPT-level AI (1 Nov):** I said this is not reachable by training the Sati models on free compute. The honest route is Sati AI answering through the AI Gateway with a frontier provider (e.g. Bedrock Claude), grounded in retrieval. That costs money per call and needs the owner's decision; not done.

## Next session should

- Make the Incidents list native next (same `/incidents` data), then a native Sati AI chat on `/agent/ask`.
