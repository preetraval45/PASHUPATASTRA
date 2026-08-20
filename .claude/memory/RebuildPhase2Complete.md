# Rebuild Phase 2 complete — the demo looks finished

- **Date:** 2026-08-20
- **Phase:** Rebuild Phase 2 (docs/REBUILD.md), R9–R17
- **Commit(s):** bdfebfc, 051964a, 850ef02, dd8482e, 88a7a7e, eeaa39f, 7d0f497, ec1b67c, fe4f6a5

## What changed

`pashupatastra.vercel.app` now has a deliberate type pairing, measured contrast
in both themes, a scenario picker, empty states that lead somewhere, per-route
loading skeletons, a responsive layout down to 375px, a full favicon set and
per-page SEO metadata with a social card.

Phase 2 is closed. Phase 3 (the chat agent) and Phase A (the agent that watches
the owner's machine) are both unstarted.

## Why

The prompt's §2 asked for a version that "looks and feels finished even before
the chat exists". That is what this phase was.

## Decisions made

- **Fonts self-hosted via `next/font`** — a visitor's browser makes no request
  to Google. A security console reporting every page view to a third party
  argues against itself.
- **Inter was already assumed**: `globals.css` had been asking for `cv02`/`cv03`
  /`cv04` since it was written, and those are Inter character variants that had
  been inert on a system font.
- **Contrast is measured, not read off the palette** — badges tint their
  background with alpha over a panel, so the colour behind the text only exists
  after compositing. `scripts/verifycontrast.py` composites in a real browser.
- **The scenario picker is links, not a Simulate button** — writing state on
  Lambda lands in one container and the next read may reach another. Tested: a
  POST's audit record survived six reads, which is the bad case. Waits for R18.
- **Tables stop being tables below `sm`** — CSS-only via `data-label`, so the
  markup stays a real table for screen readers and wide viewports.
- **No `favicon.svg`** — the artwork is raster; an SVG wrapping a PNG gains
  nothing. Needs the vector redraw ROADMAP.md already owes.

## Traps worth remembering

- **React 19 hoists `<title>`** — an SVG `<title>` tooltip was emptied
  server-side, causing a hydration mismatch that re-rendered the whole map on
  every load, invisibly.
- **`metadata.icons` replaces Next's file conventions** rather than adding to
  them; a partial list silently dropped the 512px icon and apple-touch link.
- **`app/favicon.ico` emits its own `<link>` regardless**, claiming
  `sizes="16x16"` for a file holding 32 and 48 too. Serve it from `public/`.
- **`title.template` double-appends** if a page adds the site name itself.
- **Six overflows, one mistake**: flex and grid items size to their content
  unless told otherwise. Four `min-w-0`, one `break-words`, one `flex-wrap`.
- **Local agreement is not evidence for a layout bug.** The grid overflow passed
  locally and failed live, twice.

## Open questions

- The **Google Search icon** question was raised four times and never answered.
  `logo.png` is a 3:1 lockup, unreadable at 48px; the square spear is in the tab
  and at `/favicon-48x48.png`. Still the owner's call.
- Search Console submission is the owner's to do; nothing in code makes Google
  show a favicon on any timeline.
- **Whether the public demo is worth continuing at all.** The owner said the
  site should show real protection of their machine, not invented incidents.

## Next session should

- **Ask which the owner wants: Phase 3 or Phase A.** Phase A (R30+) is what they
  actually asked for — an agent watching this desktop. Phase 3 (R18+) builds the
  chat agent on the demo, and needs the Anthropic API, which is not free.
- If Phase A: R30, then **R31 (the privacy allowlist) before any collector
  gathers anything**.
