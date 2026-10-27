# Owner reading attested; RP-15 waiting on keys

**Date:** 2026-10-27

## Why
The owner said all reading tasks are complete, and that RP-12/13 were done. No written answers and no `rp13.yaml` exist in any branch.

## Decisions
- RP-05, 10, 12, 16, 20, 25 are ticked as *owner-attested* (done-when is "can explain"). The wording says no written answers were committed.
- RP-02 and RP-08 stay `[~]`: their done-when is an artefact (a GPT notebook plus a note; a training loop).
- RP-13 is not ticked: the keys are the evidence, and they must be committed alone and first. The template now also proposes keys for SC-0001..0008; SC-0002 and SC-0008 need a DECIDE.
- RP-15 is fully wired (`diagnosis-incidents.yml`, with an order gate). It triggers on pushes to benchmark/incidents/**.

## Next session
- When the owner sends keys (chat or file): commit `benchmark/answerkeys/rp13.yaml` alone, under the owner. Then build SC-0009..0020 and add label/options to SC-0001..0008 from the keys, in a later commit. That push triggers the RP-15 run.
