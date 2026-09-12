# Later is not the same as caused by, and you cannot act on what you had not seen

- **Date:** 2026-09-04
- **Phase:** Phase 5C — Sati, deeper (R72)
- **Commit(s):** pending

## What changed

`packages/core/pashupatastra/counterfactual.py` estimates what acting on one
entity at one moment would have prevented, from the causal chain placed in time
by the events each step cites and the access edges saying what depends on what.
`/incidents/{id}/timeline` offers the moments; `/incidents/{id}/counterfactual`
answers, refusing with a 422. `components/counterfactual.tsx` renders it.
`what_if_we_had_acted` is the tool, declared on `ANALYST`; prompt rule 9,
version 8. `scripts/verifycounterfactual.py` re-derives every claim
independently. `app/graph.py` gained `chain_times`, shared by route and tool.

## Why

This produces the single most quotable number the console can emit — "acting at
10:30 would have prevented ninety minutes of intrusion". A quotable number ends
up in a slide, detached from its caveats, where nobody can check it. So every
design decision here is about what the number is not allowed to include.

## Decisions made

- **A step is pre-empted only if it is later *and* downstream.** Counting
  everything after the intervention is post hoc reasoning, and it inflates the
  number. `relations.py` refuses the same conflation one layer up and the
  correlator's adjacency gate one layer down; see [[IncidentRelations]].
- **An intervention cannot precede the first record naming the entity.** The
  task's own example asks about 09:14 when the first sighting is 10:27 — that is
  a question about clairvoyance, not response time, and answering it yields a
  large avoided-impact figure no operating speed could deliver. This is the
  single most important rule in the module.
- **The boundary is inclusive.** Acting exactly at the first observation is the
  fastest possible response and must stay askable.
- **`unavoidable` is rendered with equal weight to `prevented`.** An estimate
  showing only its winnings is an advertisement. Not behind a disclosure — R68's
  argument about putting doubt one click further away than the conclusion.
- **Two assumptions travel in `basis`**: the block works immediately and
  completely, and the attacker does not take another route. Neither is settled
  by any record. They are what makes this an estimate rather than a claim, and
  they are the first things a retelling drops.
- **Steps are dated from their earliest evidence.** Dating from the last
  confirming observation reports the intrusion as later than it was, which
  shortens every gap this measures.
- **Untimed steps are excluded and named.** Assumed early they inflate, assumed
  late they deflate; either is a thumb on a scale that is entirely a comparison
  against one moment.
- **The avoided set comes from the chain, not the reach.** Reachability is what
  could have been touched; the chain is what was.
- **`chain_times` is shared between route and tool.** Two implementations would
  be two answers to "when did this step happen", and the page and the agent
  would disagree about the one number the feature produces.
- **The tool defaults to the earliest defensible moment.** It is the interesting
  question, and the one a model can ask without inventing a timestamp it would
  place before anything was observed — then read the refusal as a broken tool.

## Open questions

- **`avoided_users` is 0 on the beaconing incident**, because its entities carry
  `estimated_users: 0`. Truthful, and it means the headline "cost of the gap"
  number on that incident is a step count and a duration, not people affected.
  Whether the demo topology should carry user estimates on hosts is an owner
  call — inventing them to make the number look better is the thing this module
  exists to prevent.
- **The page asks only about the first step's entity.** A moment picker would
  mostly produce refusals a reader would read as breakage, but it does mean the
  screen shows one counterfactual rather than the comparison the task's phrasing
  ("at 09:14 *instead of* 10:31") implies.
- **Not measured against a live model.** Whether Sati calls the tool rather than
  estimating is the clause only a live run settles. Rules 5, 6 and 8 each needed
  a measurement; assume rule 9 does too.

## Next session should

- Run `python scripts/verifycounterfactual.py --api <url>` without `--no-page`
  once the site is up, and ask the deployed agent a "what if we had acted
  sooner" question to exercise rule 9.
- R73 (argue the other side) needs only R68 and is the last task before R74
  closes the phase.
- The pre-existing CI hazards from [[DraftDocuments]] are still open: unpinned
  `fastapi`/`ruff` drift, and `INC-2026-0810` citing events that do not exist.

## Bugs found while building this

- **`ToolBox` walked topology through the entity store.** `blast_radius` exists
  on `MemoryGraph` and `DynamoStore` but not `PostgresStore`, so the existing
  `blast_radius` chat tool worked in tests and on the deployment and would raise
  on a Postgres deployment. Now routed through `GraphStore`, which answers on
  all three. Fixed here rather than left, because two topology sources in one
  class is worse than either.
- **The verify script turned a 404 into an empty reach** and so reported six
  genuine downstream steps as fabrications. It was reading `/entity/` where the
  route is `/entities/{key:path}`. A checker that reports its own blind spot as
  the system lying is worse than one that does not check, because the two are
  indistinguishable in the output. It now separates "nothing depends on this"
  from "the check could not be made".
