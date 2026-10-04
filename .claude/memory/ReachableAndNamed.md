# Reachable and named

- **Date:** 2026-10-04
- **Phase:** Phase 5G — Reachable, then convincing (REBUILD.md)
- **Commit(s):** pending

## What changed

The origin of both names is now allowed, in exactly one place on the site.
CLAUDE.md was amended to permit it, and it ships as *The names* on
`/how-it-works` (R120). Sati is always introduced as *Sati, the investigation
agent*. Feed indicators are defanged in two layers (R115): the API at source
(another session's work, the same day) and the web before render
(`apps/web/lib/defang.ts`). `scripts/verifydefang.py` proves no live value is
served.

## Why

Visitors reported a *website restricted* page. The likeliest cause was the
Observatory serving live malware hosts and C2 addresses, which content filters
classify the whole host by. The owner explained the names (Pashupatastra is
Shiva's weapon; Sati is Mata Sati / Parvati) and wanted that meaning kept and
told rather than replaced. *Sati* also names widow-burning in common English, so
a bare first mention is ambiguous.

## Decisions made

- Names kept; the misreading is handled by context (descriptor + origin note),
  not by renaming. The owner's call, recorded in BRAND.md *The names*.
- The origin note is attribution, not ornament: one passage, no imagery,
  nowhere else. Everything else stays "names only".
- Publisher advisory links (abuse.ch, CISA, NVD) stay live even when their path
  contains an indicator. They are how a reader checks a claim.

## Open questions

- Which filter actually blocked visitors (R116): needs a block-page screenshot
  from the owner.

## Next session should

- **R122 first.** The production API is `degraded`: memory-only storage, no
  feed ever polled, and code older than R76. The live Observatory is empty for
  everyone. Fixing it needs AWS access, which a Claude session here was denied.
  The owner runs buildlambda → deploylambda → schedulefeeds → one
  `ingest_feeds` invoke.
- Then run `scripts/verifydefang.py` against production and tick R115.
- R123: ransomware.live `/v2/recentvictims` returns 404.
