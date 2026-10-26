# Kushmanda v1 results and the v2 redesign

- **Date:** 2026-10-26
- **Phase:** Block H — Real-data models (RP-65)
- **Commit(s):** pending

## What changed

Kushmanda v1's Kaggle GPU run is committed as it came out
(`docs/research/models/kushmanda.md`). v2 is built and waiting for its run.
Changes in v2:

- NVD CVE descriptions join the corpus.
- The model is smaller (about 17M parameters) and uses dropout.
- Grounded tuning: each question comes with 3 passages, the answer cites one,
  and about 10% of questions have no answering passage and must abstain.
- New scoring in `sati/lm/evaluate.py`, against a lexical baseline and chance.
- A CPU smoke job (`kushmanda-smoke`) in `train-sati.yml`.

Separately, every bot push loop now fails loudly. A loop ending in `sleep`
exited 0, which hid the lost BGL results commit on 19 Oct.

## Why

v1 overfitted by step 400 of 8,000, with 34M parameters on 1.09M tokens. It
scored 0.000 on held-out questions asked without context, which tested memory,
not answering. Rule 1 means Sati can only use a language model that answers
from retrieved evidence, so grounded tuning is both the right test and the
only servable role.

## Decisions made

- NVD is used for pretraining only, not tuning. Its descriptions would make
  trivial copy questions.
- The report derives its overfitting statement from the training curve and is
  never typed by hand.
- The v1 report branch is kept, so the committed v1 table still reproduces.

## Next session should

- After `kushmanda-smoke` passes in CI, push the Kaggle kernel (v2 defaults),
  then commit the results, write the Kushmanda model card, and update RP-65.
- If v2 still overfits early, cut steps or width before adding more data.
