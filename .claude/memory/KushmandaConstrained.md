# Kushmanda constrained decoding results (RP-44)

**Date:** 2026-10-26

## Why
RP-44's done-when is "100% of outputs validate". The constrained decoder existed with tests; this records the Kaggle measurement.

## Decisions
- Results are a generated table (`sati.lm.constrainedreport`, in `scripts/reproduce.py`), like every other model page.
- The paper and card state the finding as "fixes the form, not the choice": valid outputs 1.000, lookup 0.528 → 0.604, still far below word overlap 0.962. Serving should take IDs from retrieval.
- RP-44 stays `[~]`: the JSON hypothesis schema needs RP-13's owner-labelled incidents.

## Next session
- Kernel `sati-kushmanda-constrained` reruns by `kaggle kernels push` from `kaggle/kushmanda-constrained/`.
- Pending: Chandraghanta v1 (kernel v4) and the RCAEval diagnosis workflow table.
