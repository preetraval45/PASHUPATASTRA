# Chandraghanta results; RP-61 done

- **Date:** 2026-10-26
- **Phase:** Block H — Real-data models
- **Commit(s):** pending

## What changed

Chandraghanta's results, report, model card and Models page section are
committed, and RP-61 is ticked. CIC's garbled web-attack labels are cleaned in
the loader for future runs, and at display time for the committed results.
The report now states measured findings computed from the results.

## Why

These are the paper's clearest split-leakage evidence. On CIC-IDS2017 the same
model scores F1 0.997 on a random split and 0.453 on unseen days.

## Decisions made

- **The results file is left untouched.** Its label names stay as the run
  produced them; cleaning happens in the report and on the page, so the file
  remains a genuine run output.
- **Kaggle mount path:** datasets appear under
  `/kaggle/input/datasets/<owner>/<slug>`. Search `/kaggle/input` with
  `followlinks`; never hard-code the path.

## Next session should

- §7 or §8 of the paper (owner-shared): the split comparison belongs in
  failure analysis (RP-34/35).
- Consider a Chandraghanta v1: anomaly scoring combined with the classifier,
  since the two fail on different families.

## v1: either detector (26 Oct)

`chandraghanta-v1 (either)` flags a flow if the classifier or the benign-only
PCA does; they fail on different families. It runs on Kaggle CPU via
`kaggle/chandraghanta`. Also added this session: PAPER §7.2, guarded by
`testpaper.py`.

## v1 result (2026-10-27)
"Either detector" (v0 OR benign-only PCA) is a negative result. It catches CIC infiltration (0.722) but flags 5.8% of benign flows instead of 0.1%. CIC F1 is 0.449 against 0.453, and UNSW 0.733 against 0.897. v0 stays the served model; the v1 row stays in the table as a recorded negative.
