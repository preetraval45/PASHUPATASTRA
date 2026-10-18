# ConsoleAsApp

- **Date:** 2026-10-18
- **Phase:** Block G — RP-48, RP-49, RP-50 (branch `ui-redesign`)
- **Commit(s):** pending, on branch ui-redesign

## What changed

- Route groups, with no URL changes. `app/(site)/` holds the public pages
  (/, how-it-works, evaluation, impact, press) with the old header and footer.
  `app/(console)/` holds the app: `ConsoleFrame` in components/sidebar.tsx is a
  collapsible sidebar plus a slim top bar. `(console)/(padded)/` is for
  document-like pages that scroll. `/ask` sits outside it and fills the window.
- Ask is full screen. An incident rail is on the left and the conversation is
  centred, with the composer pinned to the bottom. A facts panel sits on the
  right at xl. The empty screen is a welcome with starter cards.
  Conversations are kept per incident in localStorage (last 40 turns).
- Model picker. `GET /api/v1/models` is an allow-list built from config: the
  default chain plus `ollama:<name>` for `fallback_model` and `chat_models`.
  `/agent/chat` takes `model` and refuses unknown ids with a 422 before the
  incident lookup. `gateway_for(id)` keeps one cached gateway per choice.
- components/listbox.tsx is an ARIA listbox that replaces the native select.

## Why

The owner said the site reads like a website and wants an app: a full-page
chat, a choice of model, and interactivity. It is O-1A demo material.

## Decisions made

- The sidebar label is "Ask", not "Ask Sati". BRAND.md requires the first
  mention of Sati on a page to read "Sati, the investigation agent", and the
  sidebar would be that first mention everywhere.
- The answer cache already keys on the provider's model, so switching models
  never serves another model's cached answer.
- The STARTERS text is unchanged, because it is part of the cache key. The
  descriptions live separately in STARTER_HINTS.
- The scripts/verify*.py checks that look for `header nav[aria-label='Primary']`
  only hold on the public site now. The console's nav is in `aside[data-sidebar]`.

## Open questions

- The production API (Lambda) has no `/models` until the API is redeployed, and
  that needs AWS credentials the owner hasn't configured. Until then the
  preview hides the picker, because `getModels` returns null.

## Next session should

- RP-51 (welcome page), RP-52 (dashboards), RP-53 (interaction). Merge to main
  only after the owner has seen the preview.
