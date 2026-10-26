# Block F: Sati-LM bookkeeping and constrained decoding (RP-41 to RP-44)

- **Date:** 2026-10-26
- **Phase:** Block F — Sati-LM
- **Commit(s):** pending

## What changed

- **RP-41 ticked:** Kushmanda's BPE uses 47.75 tokens per line against
  GPT-2's 50.27.
- **RP-42 and RP-43 partial,** with the deviations stated: security text, not
  logs, because of LogHub's licence; 16.9M parameters.
- **RP-44:** `sati.lm.constrained` writes only identifiers present in the
  context and cites their passage. `constrained_eval` runs on Kaggle with the
  private model attached (`kaggle/kushmanda-constrained`).

## Decisions made

- **The model's own abstention is kept.** Constraints apply only when it
  answers, so its ability to decline is not removed.

## Next session should

- Read `constrained.json` from the Kaggle output. If exact match rises above
  free decoding (0.528 on lookup), serve with constraints.
