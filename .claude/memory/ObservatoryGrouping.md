# Observatory grouping (R56)

## Why

The Observatory rendered one card per feed report. abuse.ch publishes a
submission every time somebody sees a URL, so the live feed had **43 cards for
one IP** and 200 reports covering 108 distinct indicators. The page read as
script output rather than intelligence, and the other 107 indicators were
buried under the repetition.

## Decisions

- **Grouped server side** (`services/api/app/feeds/grouping.py`), for the same
  reason the incident sub-graph is filtered server side: the browser should not
  receive 200 rows to render 108, and the collapsing has to be testable against
  a fixture rather than asserted about a component.
- **`GROUPING_WINDOW = timedelta(hours=3)`**, named because it appears in the
  count, in the phrase the page prints, and in the test.
- **The window is rolling relative to each indicator's own newest report**, not
  to the wall clock. Anchored to now, an indicator last seen yesterday reports
  zero recent sightings, and the number a page prints becomes a function of when
  the page happened to load.
- **`active` follows the latest report's status**, not "any report said online".
  The `busy` fixture exists to pin this: its oldest report is offline and its
  newest is online, so an any-or-all rule gets one of them wrong. Carrying the
  optimistic reading forward leaves dead infrastructure on the board as a live
  threat.
- **Ordering is recency, not volume.** 43 sightings of something last seen on
  Tuesday matters less than one sighting from ten minutes ago. A test asserts
  the two orderings are distinguishable in the fixture, so it cannot pass by
  coincidence.
- **The offline half is one collapsed panel, outside the day timeline.** A
  day-by-day chronology of infrastructure that has already gone is a list of
  things that stopped mattering.
- **Nothing is discarded.** Every report keeps its timestamp, reporter, tags and
  status behind an expander. Eight independent sightings is itself a fact about
  an indicator — now a fact the page states rather than a scroll the reader
  performs.

## Verification

Against the deployed site, not a fixture: 60 reports → 34 indicators, 0
duplicate identifiers at the top level, 24 active / 10 offline **matching the
API's own split exactly**. That last comparison is the point — the checker does
not decide what the answer should be, it asserts two independently computed
numbers agree. This session's recurring failure has been checks that were green
while measuring nothing.

## For the next session

- Pre-existing and unrelated: `packages/core/tests/testpib.py` hardcodes
  `CORPUS = "benchmark/incidents/pib"` as a **relative** path, so it loads zero
  scenarios and fails 8 tests when pytest runs from `packages/core`. All 27 pass
  from the repo root. A cwd-dependent test is a trap; worth resolving the path
  against the repo root.
- `app/observatory/page.tsx` fetches `LIMIT = 60` reports. The API can group the
  full 200. Raising it is a one-line change if the page should show more.
- Next: **R57** (build info panel — stack read from manifests, not typed from
  memory), then **R58**, then **R59** closes Phase 5A.
