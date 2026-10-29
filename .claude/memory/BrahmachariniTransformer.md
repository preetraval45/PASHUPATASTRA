# Brahmacharini transformer — a negative result

- **Date:** 2026-10-27
- **Phase:** Research plan, block C (RP-30)
- **Commit(s):** this push

## What changed

Brahmacharini v1, a transformer encoder of about 20M parameters trained from scratch on Kaggle (run 2, 200 epochs), is recorded as a generated table (`docs/research/models/brahmacharini-transformer.md`, in `reproduce.py`), in the card, in PAPER §7.2 and in RP-30. Test Recall@1 is 0.391 against v0's 0.614.

## Why

About 14k procedures are too few for a 20M-parameter encoder trained from nothing. Reporting it keeps the paper honest: bigger did not win.

## Decisions made

- v0 stays served. v1's weights are not committed.
- `embed/report.py` now labels rows by key. It previously labelled every `brahmacharini*` row as v0.

## Open questions

- Would initialising from a pretrained encoder help? Not from Kushmanda, whose corpus holds the test procedures.

## Next session should

- When the TF-IDF LR rows land from CI, update the Brahmacharini and Skandamata cards, then run `scripts/ieeeupdate.py`.

## Later the same day

- The TF-IDF LR beat Brahmacharini v0 in CI (0.646 vs 0.614). `embed/run.py` now adds a fused row, with the weight chosen on validation, in commit 87e5026. Waiting on CI.
- Try panels for Kalaratri and Chandraghanta are in `components/trytree.tsx`. Chandraghanta's export waits on Kaggle kernel v9, which was pushed at af0d95f.
- IEEE docx regenerated, tracked by "Claude" (RP-78). Rerun `scripts/ieeeupdate.py --out "docs/research/Pashupatastra IEEE Paper.docx"` after each new result. It always builds from bcc5849.
- The IEEE paper gained two figures drawn by `scripts/ieeefigures.py` (matplotlib, installed in .venv locally): Fig. 2 places the nine models in the loop, and Fig. 4 is RQ5. The author's Fig. 2 was renumbered to Fig. 3 as a tracked change. To check the render, export a PDF through Word COM (PowerShell `Word.Application`, `SaveAs2` format 17), then read it with pypdfium2. LibreOffice and poppler are not installed.
- Chandraghanta is now served with 16 examples and scores 11 of them correctly, consistent with its unseen-family recall. Skandamata also loses to TF-IDF LR, 0.827 against 0.792.
- 28 Oct: fused Brahmacharini+TF-IDF R@1 0.673 (weight 0.90, validation-chosen) beats both; not served yet — needs the LR exported without sklearn. Site /models now names baselines readably (modelnames.baselineName) and says where TF-IDF wins.
- 28 Oct evening: the fused technique ranking is served for 'which technique is this?' only. On defence questions it misread 'file shares' as Network Share Discovery, so mitigations keep retrieval. A retrain moved served-design R@1 0.557 to 0.556, and testpaper caught it. NEVER sed a number repo-wide: it hit weights in sati_models/*.json (restored).
