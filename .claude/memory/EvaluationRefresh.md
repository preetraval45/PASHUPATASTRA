# /evaluation follows the records

- **Date:** 2026-10-26
- **Phase:** Block A — Foundations + baselines
- **Commit(s):** pending

## What changed

`buildevaluation.py` now derives the review statuses and the records note
from the run records and from git. The benchmark tables job runs it and
commits `evaluation.generated.json` together with the records. There are
3 tests in `benchmark/harness/testevaluationreview.py`.

## Why

`/evaluation`, generated on 10 Oct, still said no arm had data and that "the
language model is never tested", even after 558 LLM runs. Its statuses were
hard-coded, and the records were never committed.

## Decisions made

- A status reads "answered" only when the records show it, and it names what
  remains. Diagnosis accuracy (RP-15) stays explicitly open.
- The generated JSON is not committed from a local machine: there are no
  records locally, so only CI can produce the correct version.

## Next session should

- After the benchmark run triggered by this push, confirm that `/evaluation`
  shows the arms with data, and that `reproduce.py --check` reports
  `tables.md` as the same.
