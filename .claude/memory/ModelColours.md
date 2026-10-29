# Model colours, phone width, iPhone install

- **Date:** 2026-10-29
- **Phase:** Phase 0 — Foundation (site and app)
- **Commit(s):** pending

## What changed

Each Sati model has one accent colour (`apps/web/lib/hues.ts`), applied through the `--sp` custom property and the `.sp-*` classes in globals.css. Sati AI's specialists, the nine training levels and the Findings kinds all use it. Training opens on a progress hero (`components/traininghero.tsx`), and Findings opens on filter tiles. Thin themed scrollbars are now global (`.no-scrollbar`, `.fade-x` for chip rows). The Sati AI page fits phones again. The site installs on iPhone from Safari and gets the app look when it is opened from the home screen.

## Why

The owner found the UI unattractive (native grey Windows scrollbars, flat cards) and asked that every phone screen work and whether iOS was possible.

## Decisions made

- Hues live in `lib/`, not `components/specialists.tsx`. Values exported from a "use client" module arrive in server components as client references, not data, so the server-rendered Training page could not read them there.
- `.sp-text` mixes the hue toward ink (`color-mix`), so amber and lime pass contrast on the light theme.
- The phone overflow came from the `/ask` row lacking `min-w-0`, not from the chips. To find overflow, measure over DevTools: `scratchpad/widest.mjs` pattern, Emulation 400 px, then compare `getBoundingClientRect` and `scrollWidth`. Edge `--screenshot` at 500 px silently left stale files.
- iOS: no native build, because TestFlight needs the paid Apple account. Instead, `data-app` is also set when `navigator.standalone` or `display-mode: standalone` applies. AppHome still keys on the Android user agent server-side, so the iPhone home screen gets the website home with app chrome.

## Open questions

- Should the server-rendered AppHome also show on iOS standalone? That would need a client-side switch.

## Next session should

- Re-run the 400 px scan after any layout change to `/ask` or the console shell.
