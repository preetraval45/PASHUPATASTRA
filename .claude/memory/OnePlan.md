# OnePlan

- **Date:** 2026-10-09
- **Phase:** Phase 6 — Research (and every open phase, now merged)
- **Commit(s):** pending

## What changed

`docs/research/RESEARCH PLAN.md` is now the project's only plan file. It has
45 tasks (RP-01 – RP-45), each with an owner, steps and a "Done when" line, and
a day-by-day calendar to 11 April 2027 (paper), with a Sati-LM stretch block to
6 June 2027. ROADMAP.md, REBUILD.md, KAVACH.md, TASKS.md, the paper outline and
the website-rebuild prompt were deleted. Their 239 open tasks are one-line
entries in the plan's Backlog section; their full text is in git history.

## Why

The owner asked for one plan, and for Sati to run on models trained in this
repository rather than on a third-party LLM. Several plans side by side were
drifting from each other, so the merge also removes a source of status drift.

## Decisions made

- **Sati model family** — Sati-Detect, Sati-RCA, Sati-Embed, and later Sati-LM,
  all trained from scratch on the owner's RTX 5070 Ti. The Oracle Ollama box
  (free tier, no GPU) is the runtime backup via Gateway failover, always labelled
  with its provider, and the baseline to beat. Benchmark runs never fall back.
- **The owner writes all model architecture and training code**; Claude does
  the plumbing (generator, loaders, harnesses, serving, tables) and reviews.
- **2 × 2 arms, later 3 × 2** — giving only `naive-llm` a model would change two
  variables at once, so `pashupatastra-llm` and `pashupatastra-sati` are added.
- **Test sets are never training data** — PIB, the 20 labelled incidents and the
  external benchmark; a contamination guard enforces it (RP-18).
- **Kaal's first real piece is the incident generator** (RP-17), because a
  trained model needs thousands of labelled incidents.

## Open questions

- RP-04: CLAUDE.md defines Sati as *the agent*; the "Sati models" naming needs
  the ADR and the owner's sign-off.
- Whether `docs/O1 visa roadmap.md` is folded in too — kept for now.
- The daily cloud runner with direct pushes to main was requested but not set
  up: it still needs GitHub write access for Claude and a run time.

## Next session should

- Start with RP-01 (needs the kind cluster up) or RP-04 (naming ADR).
- Tick tasks only in `RESEARCH PLAN.md`; never create another plan file.
