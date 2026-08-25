# Resemblance is not relation

- **Date:** 2026-08-25
- **Phase:** Phase 5C — Sati, deeper (R69)
- **Commit(s):** pending

## What changed

`packages/core/pashupatastra/relations.py`: `relate(a, b)` compares two
incidents on entity overlap and caller-supplied indicators, returns the records
establishing each overlap on both sides, and reports the interval without ever
letting it decide. `related_incidents` is the tool that reaches it, declared on
`ANALYST` and gated by both locks. Prompt rule 7 and version 6.
`scripts/verifyrelation.py` computes the overlap independently and holds the
agent to it.

## Why

"Are these two related?" is a set intersection over stored records. Asking a
model to judge it replaces a checkable fact with a plausible sentence, which is
the failure the Grounding ADR exists to prevent.

## Decisions made

- **Time is reported, never decisive.** Two incidents in the same minute are two
  incidents — the correlator already says so where it groups events, and this
  must not disagree with it one layer up.
- **An overlap neither side can cite is not asserted**, and citable on one side
  only is the same failure. Those come back as `uncited` so the answer can say
  what it declined to count rather than looking more certain than it is.
- **Refs are empty on a "no".** There is nothing to cite for an absence, and
  returning refs anyway would let an answer that found no relation still look
  sourced.
- **A "no" says what it compared.** Bare, it cannot be told apart from not
  having looked.
- **The tool is not scoped to the incident's entities**, unlike `get_entity`.
  That scope exists because an open-ended entity lookup is a way to enumerate
  the estate; an incident id is already public on `/incidents`, so this widens
  what can be asked without widening what can be enumerated.
- **Indicators are passed in, not read.** `packages/core` has no store and must
  run on a laptop, so the caller maps indicator value to event ids.

## Open questions

- **The demo has no related pair.** All three security scenarios are disjoint,
  so the deployed site will always answer "no relation found". The positive path
  is covered only by tests. Either a fourth scenario that genuinely shares a
  host with an existing one, or accept that the feature demonstrates the
  discipline rather than the link — worth an owner decision, not a quiet
  invention.
- Indicator overlap is implemented and unused: the demo's `SecurityPayload`
  carries `principal` set to the entity id and no `source_address`, so there are
  no independent indicators to intersect.
- The live relation question was **not measured against a model** — the day's
  free allowance for `gpt-oss-20b` (200,000 tokens) was spent on R68's prompt
  iteration. `verifyrelation.py` reports that as a failure naming what it could
  not measure. Run it once the allowance resets.

## Next session should

- Run `python scripts/verifyrelation.py --api <local or deployed>` on a fresh
  allowance; it is the only part of R69 not yet measured end to end.
- R70 (drafts, not decisions) needs R68 and is unblocked. R94 is still open.
