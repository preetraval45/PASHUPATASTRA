# Kaggle publishing (RP-77) and all nine live (RP-76)

**Date:** 2026-10-27

## Why
The owner asked for nine datasets, nine notebooks and nine models on Kaggle, one per form, with no repeats, plus all nine models working live, with nothing labelled v0/v1/v2 on the site.

## Decisions
- **Site naming:** `apps/web/lib/modelnames.ts` maps result keys to form names and hides superseded variants. Versions appear only in the paper and the cards.
- **Serving trees:** `pashupatastra.trees` (core, no deps) evaluates exported LightGBM JSON with exact parity (test in sati/tests/testtreeparity.py). Exports live in `sati.serving.*` and `sati.rca.serve`, outside the model packages, so exporting does not retrain evaluated models.
- **Live demos** use held-out data only (Katyayani's reserved 1-in-10; SMD machine-3 for the trio).
- **Skandamata live answers** chain Brahmacharini's technique → ATT&CK links (`attack_mitigations.json`) → Skandamata order. Skandamata alone gave a wrong answer to user-worded questions.
- **Kaggle:** datasets come from `scripts/kaggledatasets.py`, with Kaggle limits asserted (title 6–50, subtitle 20–80). Research-only sources (UNSW, CIC, LogHub) are never redistributed; their datasets hold splits and results only, and their notebooks attach existing Kaggle copies.
- **Kushmanda's weights stay private.** A safety check blocked making them public, because that reverses the owner's explicit decision. It needs the owner's plain "publish Kushmanda".
- **CI:** removed the train-sati concurrency group. Pending runs were being cancelled, and with path gating their models never trained.

## Next session
- When the builder kernel finishes, download `/kaggle/working/datasets/*`, create the brahmacharini, skandamata, shailaputri, mahagauri and siddhidatri datasets, and **version** `sati-kushmanda-data` (improve the existing one, do not create a new one). Then push the remaining six notebooks.
- When katyayani.json, kalaratri.json and the Chandraghanta kernel's model.json exist, publish those three models (`scripts/kagglemodels.py`; add specs for chandraghanta/kalaratri with licence CC BY-NC-SA 4.0).
- The Kaggle CLI on Windows needs relative paths: `cd folder && kaggle ... -p .`.
