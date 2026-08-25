# An empty structured field is a claim, not a blank

- **Date:** 2026-08-25
- **Phase:** Phase 5C — Sati, deeper (R68)
- **Commit(s):** pending

## What changed

`chat_answer_v1` gained `considered` — the readings the evidence also admitted,
each with the refs that closed it — verified against retrieved evidence exactly
as citations are. The chat renders it open, and renders the step trace with the
records each lookup read. `context.build` now gives every hypothesis its own ref
and includes `contradicted_by`. `gateway._finalise` asks the reformat to fill
every field the schema carries. Prompt version 5. `scripts/verifytrace.py`.

## Why

R68 asks for the intermediate steps, and three of the four things standing in
the way were pre-existing defects rather than missing features.

## Decisions made

- **`contradicted_by` reaches the agent, and each hypothesis gets its own ref.**
  Every hypothesis had gone over as `#hypothesis` with the contradictions
  stripped: two opposite claims under one identifier, and the doubt deleted. The
  agent could not name what ruled an alternative out because it was never told
  there was one.
- **The reformat retry names the schema's fields.** groq's `gpt-oss-20b`
  honours `response_format` alone and ignores it once tools are on the request,
  so *every* tool-carrying turn is reformatted. The retry's "do not add anything
  you did not already say" read as leave-it-empty. The safeguard against
  invention stays — it is load-bearing — but an empty field is an assertion that
  there was nothing to put there, and it was reaching the screen as "nothing was
  ruled out". Generic wording, because `packages/core` must not know what
  `considered` is.
- **Rule 6 is unconditional and imperative.** Measured through three drafts on
  the live model: principle → empty; block shape but conditional → empty; plain
  instruction + fixed reformat → correct. A conditional rule is one the model
  gets to decide it has already satisfied. Same lesson as R94's
  `lookup_advisory`.
- **A rejection that names nothing and one that names something non-existent are
  the same failure**, and are collapsed into `dropped_considered` together.
- **The rejections render open, the mechanical steps render collapsed.** A
  conclusion is already more persuasive than the doubt beside it.

## Open questions

- The model applies rule 6 where the question bears on the alternative and not
  otherwise — narrower than the text says, and the behaviour we want. Left
  alone rather than reworded, because the wording that produced it is the one
  that made the field populate at all.
- **R94 is still open** (reopened in R67): the `ws-0148` SMB question is
  declined at hop 0 with no tool call on the deployed agent. Worth re-measuring
  now that the reformat no longer empties fields — the two may be the same bug,
  since a prose answer reformatted without tools could equally lose a tool call
  that did happen.
- The free tier has two limits and the binding one is daily: 8,000 tokens per
  minute and **200,000 per day**. An afternoon of prompt iteration against the
  live model spent the day's allowance, and the last `verifytrace.py` run could
  not repeat its lookup half. It fails naming what it could not measure rather
  than passing, which is right — but it means the checker is not runnable
  repeatedly on the same day.

## Next session should

- R69 (reasoning across incidents) needs R68 and is now unblocked — or R94
  first, since R95 depends on it and it is known-broken on the deployment.
- R68 is not deployed. Phase 5C deploys at R74.
