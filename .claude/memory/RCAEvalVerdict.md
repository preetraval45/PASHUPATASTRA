# RCAEval diagnosis verdict (RP-33)

**Date:** 2026-10-27

## Why
The RP-33 LLM comparison finished (run 40405365611). Paired significance was added so the paper can state the result as a claim, not a point estimate.

## Decisions
- `scripts/rcaevaltable.py` now adds Katyayani-against-each rows: exact McNemar on RCA@1, Holm across comparisons. The table job installs packages/core for `pashupatastra.significance`.
- Headline: Katyayani (real RCAEval, other systems) 0.930 against llama3 0.550, qwen2.5:7b 0.510 and loudest 0.660; every Holm p ≤ 1.4e-06. It is in PAPER §7.2.
- Retraining moved Shailaputri and Siddhidatri numbers (LightGBM CPU nondeterminism). The paper §7.2 and the two cards now match run 40406026750. Cards carry a note that the generated table is authoritative.

## Next session
- RP-34: extract every wrong diagnosis from `benchmark/results/rcaeval/*.jsonl` into a review sheet with proposed categories (the owner assigns them).
- The testpaper guard catches drift in §7.2 only, not in cards. Consider generating card metric tables.
