# CI fixes, 26 Oct: feeds test, Next.js advisory, results pushes

- **Date:** 2026-10-26
- **Phase:** Block G — Product
- **Commit(s):** pending

## What changed

- **api job.** The `feeds` test fixture now stubs the attack feeds offline.
  They were added after the fixture and fetched the live internet, so a new
  ransomware.live post failed CI.
- **ThreatFox.** The feed is reported as withdrawn: its bulk export returns
  410, and abuse.ch now needs an Auth-Key.
- **dependency audit.** Upgraded `next` from 15.5.25 to 15.5.28 for a
  critical advisory (cache poisoning; image-optimisation RCE). Build info was
  regenerated to match.
- **Training pushes.** Every results commit goes through
  `scripts/pushresults.sh`. It saves the files, resets to origin/main, lays
  them back over the checkout and pushes. Three jobs had failed on rebase
  conflicts in the results files.

## Decisions made

- Pass `pushresults.sh` exact files, never shared folders. Otherwise a stale
  copy of another job's results would overwrite newer ones.
- Read CI logs with the git credential helper's token: use
  `git credential fill`, and never print the token.

## Next session should

- If abuse.ch is wanted back, get a free Auth-Key, store it as a secret, and
  rewrite `fetch_threatfox`.
