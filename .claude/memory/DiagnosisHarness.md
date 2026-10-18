# DiagnosisHarness

- **Date:** 2026-10-18
- **Phase:** Block B — RP-14 done
- **Commit(s):** this push

## What changed

benchmark/harness/diagnose.py defines Case, Diagnosis, score() and Report.
scripts/benchdiagnosis.py loads benchmark/incidents/*.yaml fixtures that have
`root_cause_label` and `options`, then runs `llm:<model>` diagnosers through
baseline_gateway with the `diagnosis_v1` schema.

## Decisions made

- The PIB YAMLs carry no telemetry, and their descriptions leak the answer.
  Diagnosis is therefore scored on the labelled SC fixtures (event signals),
  which need closed answer keys. The owner adds them in RP-13: 12 new specs,
  with keys committed first.
- `sati-rca` is not run on the SC fixtures: Katyayani needs metric series,
  and it is scored on RCAEval instead.

## Next session should

- RP-13 Claude part, once the owner writes the 12 specs: build the fixtures
  and add `root_cause_label` and `options` to all 20.
