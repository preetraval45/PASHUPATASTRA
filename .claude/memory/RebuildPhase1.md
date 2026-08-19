# Rebuild Phase 1 — R1 to R3, and the plan they run against

- **Date:** 2026-08-19
- **Phase:** Rebuild Phase 1 (docs/REBUILD.md)
- **Commit(s):** 239440b, 5c21972, 61b8337, b67be83, 86668e1

## What changed

`docs/REBUILD.md` turns `pashupatastra-website-rebuild-prompt.md` into 29
dependency-ordered tasks. R1–R3 are done: the wordmark is one text node, the
entity model gained `account`, `network_flow`, `asset` and `process`, and a
causal step can carry a MITRE ATT&CK mapping. `scripts/verifyui.py` drives a
headless Chromium so "it renders correctly" is checked rather than asserted.
The header now uses the owner's `logo.png` lockup, trimmed and re-encoded.

## Why

The site was an SRE demo whose only incident was a database outage. The rebuild
re-themes it to blue-team security. The prompt insists this is a data-model
change rather than a copy change, and it is right: a "security" console whose
action registry says `restart_service` reads as a skin.

## Decisions made

- **Sequenced tasks over phases** — a task can be named ("do R7") and finished.
  The prompt's own instruction was to not start Phase 3 with Phase 1 half-done,
  and a phase is too big a unit to hold anyone to that.
- **Add the security kinds and actions, do not delete the infrastructure ones**
  — `restart_service`, `scale_service` and `rollback_deployment` have executors
  verified against a live kind cluster, and 685 tests depend on them. Tag by
  domain and serve one domain per deployment instead. The site looks identical;
  the verified work survives. **Flagged to the owner and not yet contradicted.**
- **`ACCOUNT` is not `USER`** — one can log in and be disabled, the other is a
  number in an impact estimate. Merging them would make "1,200 users affected"
  and "one account compromised" the same statement, and blast radius feeds
  effective risk.
- **`AttackTechnique.url` is derived, never stored** — a stored URL can drift
  from the id it points at.
- **DynamoDB, not RDS, when persistence arrives (R18)** — its free tier does not
  expire and RDS's dies at twelve months.
- **The header name lives in `alt` only** — the artwork contains the wordmark,
  so setting it as text beside the image is what produced `PASHUPASHUPATASTRA`.

## Open questions

- The owner asked for `logo.png` as the **Google Search icon**. Google needs a
  square favicon ≥48×48, and this lockup is a 3:1 band on a square canvas — at
  48px the script wordmark is unreadable. `Pashupatastra icon 1` (square spear)
  is the legible option. **Unresolved; raised, not yet answered.** R15 owns it.
- Whether the infrastructure actions should be genuinely deleted after all.
- Anthropic API spend for the chat agent (R19) has no free tier and no budget
  set yet.

## Next session should

- R4 — the security action registry, with a domain tag so `/api/v1/actions`
  serves only the 14 security actions. Unblocked, and the largest visible
  change left in Phase 1.
- Then R5 (three scripted incidents), which needs R2, R3 and R4.
- R6 and R6b are recorded defects, not features: evidence ids cite events that
  do not exist, and `/infrastructure` throws React #418 at every viewport.
