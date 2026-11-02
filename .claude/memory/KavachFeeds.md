# Kavach 7.4 — feeds as data, and the disclosure policy

- **Date:** 2026-11-02
- **Phase:** Kavach Phase 7.4 + Phase 6.2/12.7 (RESEARCH PLAN backlog)
- **Commit(s):** 8ccb9c1 (disclosure), 5ad5088 (feed screening), this push (memory test)

## What changed

`intel_evidence` (agent/context.py) now screens advisories with Kavach like incident evidence — it had passed feed text to the model unflagged. testfeedpoisoning.py drives a hostile KEV entry through the real parser to an obedient model; testintelmemory.py pins that only the loop writes Smriti. `.github/SECURITY.md` + `/.well-known/security.txt` publish a disclosure process via GitHub private vulnerability reporting.

## Why

Publishing words where we poll is the cheapest injection; the plan asked for a poisoning test and the test found the gap.

## Decisions made

- No personal email in security.txt: Contact is the GitHub advisory URL, so the owner must enable private vulnerability reporting (Settings › Code security) or the link 404s.
- block_ip lands in tier `senior`, not `approval`; tests assert "not autonomous" rather than a tier list.

## Open questions

- Has the owner enabled private vulnerability reporting? (Unauthenticated API rate-limited when checked.)

## Next session should

- Remaining 7.4 item is done; next Kavach candidates: 7.3 per-record provenance audit, 10.3 prompt-injection defence across tools.
