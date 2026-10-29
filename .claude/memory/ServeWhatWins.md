# Serve what wins, and only after it is measured

- **Date:** 2026-10-28
- **Phase:** Sati models (RP-79, RP-80, RP-81)
- **Commit(s):** 4478756, 813e1d3, 18eaefd

## What changed

- **Brahmacharini:** fused with its TF-IDF classifier, now served for "which technique is this?" only.
- **Skandamata:** its TF-IDF classifier is exported with a `serve` flag. The flag is set from the same run's held-out comparison, and the API uses the classifier only when it is true.
- **Kalaratri and Chandraghanta:** live verdicts now say why, through `trees.explain` (ablation).
- **Mahagauri v3 and Kalaratri novelty features:** measured and recorded. Both are modest results.

## Decisions made

- **A model is served only where its evaluation is the same task.** The fused technique ranking misread a defence question ("file shares" became Network Share Discovery), so defence questions keep retrieval, with a regression test.
- **Jobs commit only their own model files.** `pushresults.sh` overlays files, so committing a whole folder can roll back another job's newer files.

## Next session should

- Check `mitigation_classifier.json`'s `serve` flag and the "pruned, as served" row in skandamata.md, then ask a defence question live.
- Check Chandraghanta kernel v10 for the v3 row (classifier fused with PCA, weight chosen on held-out families).
