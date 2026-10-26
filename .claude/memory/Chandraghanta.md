# Chandraghanta v0: network intrusion detection (RP-61)

- **Date:** 2026-10-26
- **Phase:** Block H — Real-data models
- **Commit(s):** pending

## What changed

Added the `sati.netdetect` model, the `sati.sources.netflow` loaders, 7 tests,
and the `kaggle/chandraghanta` CPU kernel. The kernel attaches
`mrwellsdavid/unsw-nb15` and `chethuhn/network-intrusion-dataset`.

## Why

RP-61 was the next untrained model. CI cannot download either official
dataset: UNSW-NB15 sits behind SharePoint and CIC-IDS2017 behind a request
form. Kaggle mirrors both and lets a kernel attach them.

## Decisions made

- **UNSW-NB15 training file chosen by size.** The released file names are
  swapped relative to the paper. The run records which file it used.
- **No scikit-learn.** The baseline is PCA reconstruction error on benign
  flows, reusing Kalaratri's `pca_scores`.
- **Leak and split measured, not assumed.** UNSW-NB15 is also scored without
  its TTL fields, and CIC-IDS2017 with a random split as a reference only. The
  by-day split is the claim.

## Next session should

- Push the kernel at a commit that includes this work and collect the results.
- Generate `docs/research/models/chandraghanta.md` with `sati.netdetect.report`.
- Write the model card and add the results to the Models page.

## Follow-up

The first Kaggle run failed: no UNSW files were found under
`/kaggle/input/unsw-nb15`. The kernel now searches all of `/kaggle/input`,
following symbolic links. It prints the input tree, and duplicate CIC day
files count once.
