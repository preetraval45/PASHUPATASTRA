# Bigger models and the servable Katyayani (27 Oct)

**Date:** 2026-10-27

## Why
The owner asked for bigger, better models using Kaggle and AWS, with the research updated.

## Decisions
- **Kushmanda v3** (Kaggle kernel `sati-kushmanda-v3`, commit 737a3fc): about 33M parameters. The corpus adds GHSA through OSV (CC-BY-4.0; only GHSA-* records, because other OSV sources carry other licences) and ATT&CK Mobile/ICS. v2's held-out questions are kept.
- **Brahmacharini v1** (kernel `sati-brahmacharini-v1`, commit d539957): a transformer encoder from scratch beside v0 in one run. It is not Kushmanda-initialised, because Kushmanda's corpus contains Brahmacharini's test procedures (leak). v0's optimizer is unchanged, so its numbers are identical (verified after retrain 92350cd).
- **Katyayani v1** (pooled with live data): a null result. It is recorded, and v0 stays.
- **Katyayani on event features** (`sati.rca.events`): real-trained 0.900/0.845/0.894 against Kaal-trained 0.265/0.490/0.265. This is the servable model (RP-75).
- **RP-75 is blocked:** the deployed API is the security console (no service metric incidents). Do not build serving code until infrastructure telemetry is deployed.

## Next session
- Collect both Kaggle outputs (`kaggle kernels output preetraval4518071604/<name> -p <dir>`). Commit kushmanda-v3.results.json + md (sati.lm.report) and brahmacharini-v1 results (sati.embed.report). Then update the cards, PAPER §7.2 and the plan RP-43/RP-30.
- Workflow edits: use line-anchored regex and validate the paths-filter block before committing. A substring anchor broke train-sati.yml once (bd10bba).
