# RP-33: Sati against LLMs on RCAEval

- **Date:** 2026-10-26
- **Phase:** Block D — External validity
- **Commit(s):** pending

## What changed

- The `llm_sample` (100 cases, by hash) was added to
  `benchmark/external/rcaeval/subset.json`, before any LLM run.
- `scripts/benchrcaeval.py` builds RP-14 harness cases from the RP-32
  adapter's label-free inputs.
- The `rcaeval-diagnosis.yml` matrix runs loudest, sati-kaal, llm:llama3 and
  llm:qwen2.5:7b, then `scripts/rcaevaltable.py` builds the table.

## Why

RP-33 asks for the best LLM baseline on the same external cases. Every
diagnoser sees identical evidence and is graded by the same harness.

## Next session should

- Read `docs/research/models/rcaeval-diagnosis.md` when the run finishes.
- Consider adding Katyayani trained on RCAEval (leave one system out) as a
  diagnoser in the same harness, for a like-for-like comparison.

## Katyayani row (same day)

The `katyayani` diagnoser trains on real RCAEval RE1/RE2 cases from the other
systems, leave one system out, using Katyayani's own features. It is the
like-for-like real-data row beside the LLMs and the Kaal model.
