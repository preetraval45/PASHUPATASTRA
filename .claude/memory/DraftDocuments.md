# A draft is a draft, and adopting one is an action

- **Date:** 2026-08-25
- **Phase:** Phase 5C — Sati, deeper (R70)
- **Commit(s):** 1eef514 (implementation), this change (roadmap tick + verification)

## What changed

`packages/core/pashupatastra/drafts.py` builds a playbook and a post-incident
report from an incident's stored records. `Line` refuses construction with empty
`refs`. `/incidents/{id}/draft/{kind}` assembles one per request and returns
`adopt_action_id` without evaluating it. `components/drafts.tsx` renders the
document with every ref as a link and no adopt button. Four registered actions —
`adopt_playbook`, `retract_playbook`, `adopt_report`, `retract_report` — at
base risk 35.

The implementation landed in 1eef514 but the R70 checkbox was never ticked and
no memory entry was written, so the phase read as unstarted. This change verified
it and closed both gaps.

## Why

Generation is a new output, not a new authority. The whole task is the gap
between "the agent wrote a procedure" and "the team follows that procedure", and
every design decision below is about keeping something in that gap that a human
has to cross deliberately.

## Decisions made

- **The citation rule lives in the constructor.** `Line` raises on empty `refs`
  rather than a validator running afterwards. Assemble-then-check tests the
  builder as written today; refusing to construct tests the builder anybody
  writes next. Same argument as `Hypothesis` rejecting empty evidence.
- **Drafts are assembled on request, never stored.** A saved draft goes stale
  against the incident it describes and the failure is silent — a report citing
  a plan step since re-scored. Built each time, it cannot disagree with it. Rules
  out draft editing and versioning without a real store decision first.
- **Labelled a draft in three places** — panel title, badge, document title.
  It is written to be copied out of a browser, and the failure mode is a
  paragraph arriving elsewhere with "draft" left behind on the page it came from.
- **35, chosen for the band and not the number.** At the original 20 these sat
  in the 0–30 autonomous band, so in an environment with no blast radius the
  agent could adopt its own draft unattended. 35 is where `disable_deployment`
  sits and it is the same shape of act: changes what happens next, breaks nothing
  now, fully reversible.
- **Adopt and retract are priced identically** because they are each other's
  rollback. A rollback priced far below the thing it undoes gets taken lightly
  during the incident where it matters.
- **`status` is a property returning `"draft"`, not a field.** A status that can
  be assigned eventually is. The approved thing is an audit record naming a
  human, never a flag on the document.
- **The route does not score the action it offers.** An endpoint evaluating the
  thing it is serving would be marking its own work; the page asks
  `/policy/evaluate` separately.
- **`verifydraft.py` resolves refs against the store rather than matching a
  pattern.** "Every line has refs" is satisfied by a line citing
  `evt-imaginary`, and a regex accepting `INC-2026-0903#chain-9` would accept
  exactly the near-miss citation it is looking for.

## Open questions

- **The infra fallback incident cites events that do not exist.** With
  `PASHU_ACTION_DOMAIN` unset, `Store.seed_demo()` seeds `INC-2026-0810`, whose
  evidence names `evt-deploy-421`, `evt-pg-connections`, `evt-api-5xx` and
  `evt-request-rate-flat` — none written to the entity store. Both drafts then
  render thirteen citations that 404, which is R59's rule broken on a supported
  path. Predates R70; the deployed security configuration never takes it. Fix by
  seeding those events or by giving the fixture refs that exist. Not done here
  because the fixture is not R70's to change — needs an owner call on which.
- **Unpinned dependencies make two CI gates drift.** `fastapi>=0.111` installed
  0.141.1 locally, which emits a single `Verdict` schema where the committed
  `openapi.json` has `Verdict-Input`/`Verdict-Output`, so
  `exportopenapi --check` fails on a version difference rather than a real API
  change. `ruff>=0.5` installed 0.16.4 and reports 29 findings in
  `packages/core` from rules that did not exist when the code was written.
  Neither is caused by R70 and both will bite the next person who runs CI.

## Next session should

- Run the page half of `scripts/verifydraft.py` — it needs playwright and a
  running site, and Phase 5C does not deploy until R74. The badge count, the
  citation links and the overflow check are the clauses still unmeasured.
- Decide the `INC-2026-0810` citation question above before R74's review, since
  that review is where a dead link on a supported configuration would be found.
- R71 (natural language to a Sigma rule) needs R70 and is now unblocked. R72 and
  R73 need only R68 and were already unblocked. R94 is still open.
