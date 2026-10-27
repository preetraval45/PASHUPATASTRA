# Vercel free-plan deployment limit

**Date:** 2026-10-27

## Why
Vercel failed with "api-deployments-free-per-day" (more than 100). Every push to main built the site, including the train-sati bot's result commits and my own small commits; there were 101 commits in 24 hours.

## Decisions
- `apps/web/vercel.json` `ignoreCommand`: `git diff --quiet HEAD^ HEAD -- .` skips the build when apps/web did not change. A git error builds (safe default).
- Unverified: whether a skipped (cancelled) build still counts toward the 100. If the limit hits again, batch pushes. Bot commits that touch apps/web/lib/models still deploy.

## Next session
- Batch website changes into fewer pushes. Gate commits on `tsc` explicitly; a failed check once still committed (faa89f8, fixed in 09e7203).
- The live site serves the last good build while the limit is exhausted.
