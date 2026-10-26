# LLM baseline results (RP-07, RP-09, RP-10)

- **Date:** 2026-10-26
- **Phase:** Block A — Foundations + baselines
- **Commit(s):** pending

## What changed

RP-07 and RP-09 are ticked, and the RP-10 entry now carries Table 5's
results. Benchmark run 39179521734 recorded all 558 pre-declared runs.

## Why

Table 1 shows every arm with n = 93, and Table 5 tests every planned pairing.
Those are the "done when" conditions for RP-07 and RP-09.

## Decisions made

- The weak LLM rows are recorded as they are, without tuning prompts after
  seeing the results; tuning after the fact would turn this into a fishing
  exercise. The plan line states the caveats: llama3's score equals the
  do-nothing rate, mistral always went off-list, and qwen hit 53–56 provider
  errors.

## Open questions

- Qwen's errors are probably timeouts from CPU inference. A rerun with a longer
  timeout would be a new, pre-declared run, not an edit of this one.

## Next session should

- RP-11 (§7 baselines draft) is unblocked, but the owner shares it. Draft only
  from numbers in tables.md.
