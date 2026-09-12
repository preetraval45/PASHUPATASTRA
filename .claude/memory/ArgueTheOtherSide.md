# A ranking is not a refutation

- **Date:** 2026-09-04
- **Phase:** Phase 5C — Sati, deeper (R73)
- **Commit(s):** pending

## What changed

`packages/core/pashupatastra/contest.py` states the case for an incident's
leading alternative and reports what answers it — or that nothing does.
`/incidents/{id}/contest` serves it, refusing with a 422 where there is no rival
worth arguing. `components/contest.tsx` renders it under the Blue Team rubric's
own heading, *the plausible and wrong explanation*. `argue_the_other_side` is
the tool; prompt rule 10, version 9. `scripts/verifycontest.py` re-derives the
adjudication independently.

## Why

The Blue Team rubric tells a player that one of the explanations is plausible
and wrong and scores them on opening the evidence that rules it out. R73 holds
the console's own diagnosis to that standard, which is what turns the rubric
from a scoring note on a game page into a demonstrated claim.

## Decisions made

- **The verdict turns only on whether something stored contradicts the rival.**
  A confidence figure is a number an author wrote; the diagnosis asserting its
  own likelihood is the claim under examination, not evidence for it. 0.86
  against 0.09 decides nothing.
- **`UNREFUTED` is the alternative winning, and it is an open question rather
  than a rival conclusion.** It says the diagnosis has not earned its place, not
  that the alternative is right. Easy to lose in a badge, so the panel and the
  tool both say it in a sentence.
- **A rival must share ground and diverge.** Share at least one observation with
  the leader, or it answers a different question; and be separated by something,
  or the two are one claim written twice. Neither holds → refuse rather than
  stage a contest.
- **Text is never compared.** Deciding sameness by wording is the
  resemblance-matching [[IncidentRelations]] refuses. Two hypotheses can be
  worded alike on different records, or differently on the same ones.
- **An unresolvable rejection is not a rejection.** Same collapse R68 makes:
  naming no reason and naming a reason that does not exist leave the reader with
  the same thing.
- **An ungrounded leader is not adjudicated.** A contest neither side can win is
  not worth staging, and reporting the alternative as beaten by an unsupported
  diagnosis would be worse.
- **The rival is credited with what the leader does not explain.** The point a
  confident diagnosis is least likely to make about its own alternative.
- **Both verdicts are seeded in the tests.** All three demo incidents rule their
  alternative out, so the case that matters most would never be exercised — the
  same silent-skip problem as [[DetectionRules]] and [[Counterfactuals]].

## Open questions

- **The demo never produces an `unrefuted` verdict.** Every scenario was written
  with its alternative properly closed, which is good scenario design and means
  the deployed site will always show *ruled out*. The more interesting screen —
  a diagnosis that has not beaten its rival — exists only in tests. Either a
  fourth scenario whose alternative genuinely survives, or accept that the
  feature demonstrates the discipline rather than the finding. An owner call,
  not something to fake.
- **The fallback infrastructure incident refuses**, because its hypotheses cite
  `evt-*` ids that were never stored — the [[DraftDocuments]] fixture problem
  surfacing a third time. R70 flagged it, R73 is now the third feature it
  degrades. Worth fixing before R74's review.
- **Not measured against a live model**, and this is the rule most likely to
  fail. Rules 8 and 9 compete with the model not having facts; rule 10 competes
  with it always being able to write the *shape* of a challenge, and with that
  shape having a direction — agreeing with the document in front of it. A model
  asked to challenge a diagnosis will nearly always conclude the diagnosis
  survives, which is the one outcome that makes the feature worthless.

## Next session should

- Run `python scripts/verifycontest.py --api <url>` without `--no-page` once the
  site is up, and ask the deployed agent to challenge a diagnosis — specifically
  on an incident seeded to be `unrefuted`, to see whether it reports a result
  that argues against what it just read.
- **R74 closes Phase 5C** and needs R68–R73, all of which are now done. It is a
  deploy-and-review task: the three verify scripts' page halves have never run,
  and none of R71–R73 has been measured against a live model.
- Decide the `INC-2026-0810` fixture question before that review.
