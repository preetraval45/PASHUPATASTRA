# Vercel deploys failed for a day on a comment key

- **Date:** 2026-10-28
- **Phase:** Website
- **Commit(s):** this push

## What changed

`apps/web/vercel.json` had a `"//"` comment key (added 27 Oct alongside `ignoreCommand`). Vercel validates the schema before building and rejected every deployment ("should NOT have additional property `//`"), so production stayed on 27 Oct's site while the local build and tests passed. Removed it, moved the note to docs/DEPLOYMENT.md, and added `lib/vercelconfig.test.ts`.

## Why

JSON config files have no comments. Vercel's error shows only in the deployment record, not in the build log.

## Decisions made

- Diagnosed read-only with the user's logged-in Vercel CLI: `MSYS_NO_PATHCONV=1 npx vercel api /v13/deployments/<id>` returns `errorMessage`. Git Bash mangles the leading `/` without that variable.

## Next session should

- After a web push, confirm production carries it: GitHub commit statuses (`/commits/<sha>/statuses`, context "Vercel"), or grep the live page.
