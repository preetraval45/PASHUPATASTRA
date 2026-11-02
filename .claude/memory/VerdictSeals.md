# Verdict seals — the excessive-agency gap

- **Date:** 2026-11-02
- **Phase:** Kavach 10.3 — audit and safety (RESEARCH PLAN backlog)
- **Commit(s):** pending

## What changed

The API signs every verdict Dharma issues (`app/engines/seal.py`, HMAC over the authority fields), and re-signs after approve/deny. `astra.execute`, `loop.remediate`, `/policy/approve` and `/policy/deny` refuse a verdict whose seal does not match. Core `Verdict` gained an optional `seal` field (core never computes it). `tests/testexcessiveagency.py` (13 tests) closes the backlog item.

## Why

Writing the excessive-agency test found that every route acting on a verdict took it from the request body: a forged `tier: autonomous` executed (dry-run in prod, but audited as authorised). Rule 2 means "issued here", not "shaped like a verdict".

## Decisions made

- Seal key derived from accounts' `_signing_key` (domain-separated), so no new secret to configure — if that function is renamed, seal.py breaks loudly.
- `adjustments` and `tier_reasons` are outside the seal: display-only, and older dashboards drop `tier_reasons` (testapi pins that).
- The core `Remediator` still accepts any non-None verdict: the benchmark arm treats the scenario risk ceiling as the grant without setting `granted_by`. Tightening it changes benchmark semantics — a separate decision.
- Verdicts issued before this deploy are unsealed and are refused; they expire in 15 minutes anyway.

## Open questions

- Should the benchmark arm record its implied grant (`granted_by="scenario:risk_ceiling"`) so the core Remediator can require `is_executable`?

## Next session should

- Keep the route set in `test_every_route_that_accepts_a_verdict_is_checked_here` current; a new route taking a Verdict must check `is_sealed`/`require_seal`.
