# OneLookEverywhere

- **Date:** 2026-10-18
- **Phase:** Block G — RP-54 extended; Block H — RP-59 datasheets
- **Commit(s):** c6cb731 (datasheets), this push

## What changed

- `.panel` is now rounded-xl and flat-filled. The `Panel` heading is a real h2
  (0.9375rem semibold), where it used to be an 11px uppercase label. Every
  page inherits both.
- Overview has the interactive `TimeBars` Activity panel, with a link to
  /analytics.
- docs/research/datasheets.md: RCAEval, NAB and SMD are MIT. UNSW-NB15,
  CIC-IDS2017 and LogHub are research-only, so the owner has to decide how
  weights trained on them get released.

## Why

The owner asked for the RP-54 look to reach "other parts as well". Changing
the shared component restyles every page at once and keeps them consistent.

## Decisions made

- The `.label` class is unchanged. It still marks tile captions and
  definition terms; only panel titles became headings.

## Next session should

- RP-51: the Home page inside the app frame.
- Check the first Sati-RCA training run, and tick RP-58 or fix it.
