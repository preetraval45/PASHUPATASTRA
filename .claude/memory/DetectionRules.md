# The rule it could honestly write was worse than the one it could invent

- **Date:** 2026-09-04
- **Phase:** Phase 5C — Sati, deeper (R71)
- **Commit(s):** pending

## What changed

`packages/core/pashupatastra/sigma.py` drafts a Sigma rule from one causal step
of one incident: `Mapping` refuses construction without refs and a source field,
`Gap` refuses one without a reason, and `draft_rule` refuses to emit a rule with
no mappable field at all. `validate` structurally checks the output.
`/incidents/{id}/detection-rule` lists what can be drafted and
`/incidents/{id}/detection-rule/{technique}` serves one; a step that maps to
nothing is a 422. `components/detectionrule.tsx` renders the mapping table, the
gaps and the YAML. `draft_detection_rule` is the tool, declared on `ANALYST`,
gated by both locks. Prompt rule 8, version 7. `scripts/verifysigma.py` checks
all three clauses independently. `app/graph.py` gained `events_by_id`.

## Why

R71 is the first genuinely generative feature, and the naive version of it is
the most convincing wrong output this codebase could produce. Asked for a Sigma
rule for SMB lateral movement, any model writes `EventID: 5145` and
`ShareName: ADMIN$` — the shape such rules have — from a store that holds
neither. The result parses, reviews well, deploys, and never fires. No
downstream check catches it: the fields are real Sigma fields and the YAML is
valid. Only somebody who knows this platform's event model can see that not one
of them is populated here.

## Decisions made

- **The mapping is deterministic; the model only decides to ask.** Which
  telemetry field corresponds to which Sigma field is a fact about `events.py`,
  not a judgement. Same split as [[IncidentRelations]], and rule 1.
- **Mapping is typed, to refuse a category error.** `payload.principal` holds
  the subject of the detection, which on a host-scoped detection is a hostname.
  It maps to an identity field only where the entity is an account; elsewhere
  the refusal is reported. A hostname in `SubjectUserName` parses, cites a real
  stored value, and is wrong invisibly.
- **`generalises` is tracked per field.** A rule keyed on `ws-0148` would have
  caught 0903 and will never catch anything else. Without the distinction every
  rule looks equally good, and an indicator list gets deployed as a detection.
- **Uncertainty is emitted into the YAML** (`x-gaps`, `x-not-mapped`,
  `x-warning`, the comment header), not just into the API response. The document
  is what gets pasted into a detection repository; the panel does not travel.
  [[DraftDocuments]]'s argument about the word "draft", applied one step on.
- **Gaps are not `falsepositives`.** They were, briefly. Two Sigma keys with two
  meanings, and filling one with the other misreports both to every tool that
  reads the document. `falsepositives` is now derived from the rule's own shape.
- **The tool does not return the rule text.** A model that retypes a
  machine-readable artefact eventually retypes it wrong, one character is a rule
  that does not parse, and nothing in the loop could catch it. Also ~600 tokens
  against an 800-token bound.
- **Prose is never parsed.** `labels.summary` names the two SMB peers a stronger
  rule would key on, in a sentence. Reading them out would make the rule depend
  on grammar.
- **pySigma is a dev dependency of `packages/core`.** Our own `validate` is the
  same author marking their own work and would accept a rule wrong in exactly
  the way we misread the spec.
- **The API tests seed their own incident.** They first read whichever incident
  the deployment held — which in the default configuration carries no ATT&CK
  mapping, so three clauses of R71 skipped while reporting green. Same class of
  problem as the fixture issue in [[DraftDocuments]].

## Open questions

- **The honest answer to the task's own example question is a bad rule.** The
  SMB step supports exactly one field, `Computer: ws-0148`. Of six rules drafted
  across the three demo incidents, one generalises. That is a truthful report of
  what this telemetry can support and it is also a thin demo. Either the
  `SecurityPayload` grows the fields a detection needs (share name, accessing
  account, event id) or R71 demonstrates the discipline rather than the
  capability — an owner decision, not something to quietly improve by loosening
  the mapper.
- **`TECHNIQUE_FIELDS` is a hand-written table** of four techniques and the one
  place here that claims something about the world rather than about our store.
  It needs a source, or a decision that four is enough.
- **Not measured against a live model.** Whether Sati calls the tool rather than
  writing Sigma from memory is the clause only a live run settles. Rules 5 and 6
  each needed a measurement to get right; assume rule 8 does too.

## Next session should

- Run `python scripts/verifysigma.py --api <url>` without `--no-page` once the
  site is up, and ask the deployed agent for a Sigma rule to test rule 8.
- R72 (counterfactuals) and R73 (argue the other side) need only R68 and are
  unblocked. R74 closes the phase and needs R68–R73.
- The two pre-existing CI hazards from [[DraftDocuments]] are still open:
  unpinned `fastapi`/`ruff` drift, and the `INC-2026-0810` fixture citing events
  that do not exist.
