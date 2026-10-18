# ShellMovedTests

- **Date:** 2026-10-18
- **Phase:** Block G — after the redesign merged to main (309a786)
- **Commit(s):** this push

## What changed

CI on 309a786 failed in two jobs. Vercel had already deployed the site, but the
CI deploy fallback was skipped.
- `web`: lib/waves.test.ts reads the incident page by path, and the page moved
  to `app/(console)/(padded)/incidents/[id]/page.tsx`.
- `api`: testbuildinfo requires `Attribution` (the one-line credit) on every
  page. It was in the root layout's footer; the console shell has no footer,
  so console pages had lost it. The credit is now at the foot of the sidebar,
  and the test checks both shells.

## Why

Two things the local runs missed. CI's API job runs pytest a second time
with `PASHU_DEMO_SEED=true PASHU_ACTION_DOMAIN=security`. And `npm test` reads
source files by path.

## Decisions made

- The owner wants everything on main and the live URL, with no preview
  branches. So before every push, run: web `npm test` plus `tsc` (filter out
  stale `.next/` types), and API pytest in both modes. Main is production.

## Next session should

- RP-51, RP-52, RP-53, straight to main, with the checks above.
