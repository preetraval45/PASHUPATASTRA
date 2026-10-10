# SatiModelsDraft

- **Date:** 2026-10-10
- **Phase:** Research plan, Block A — RP-02 set up, RP-03 and RP-04 partial
- **Commit(s):** this push

## What changed

- `docs/research/related-work.md`: the reading log, with the four RP-03
  citations checked against Crossref and arXiv. Every other field is blank for
  the owner.
- `docs/adr/SatiModels.md`: Proposed. Sati stays the agent; Sati-Detect,
  -RCA, -Embed and -LM are the models it runs on. Code goes in `packages/sati/`,
  `core` stays torch-free, models are served as a Gateway provider, and LLMs
  are kept only as baselines and a labelled fallback.
- `packages/sati/notebooks/README.md`: an RP-02 checklist and self-check
  questions. It contains no code.

## Why

The owner asked Claude to "do RP-02 and mark it complete". Claude declined to
tick it, because its done-when line is the owner's own notebook and note. When
asked, the owner chose to keep RP-02 theirs. Ticking it without that evidence
would have made the plan claim learning that hasn't happened, and the
notebook is the base for Sati-Embed and Sati-LM, which the owner said Claude
never writes.

## Decisions made

- RP-03 and RP-04 are marked `[~]`, not `[x]`. Both are done only when the
  owner's part is in.
- The ADR keeps three fields open (names, weights release, weights licence)
  instead of guessing. The repo itself has no licence yet.

## Next session should

- Once the owner decides, fill in the ADR, set it to Accepted, and update the
  CLAUDE.md naming table and GLOSSARY.md (CLAUDE.md needs the owner's approval).
- When the owner says "review RP-02", check the notebook for causal-mask and
  train/val split bugs, then tick RP-02.
