# Tasks

**Every phase of [ROADMAP.md](ROADMAP.md) and [KAVACH.md](KAVACH.md), broken down
to task → subtask → step.**

The roadmap says *what* must be true and *when*. This file says *what you
actually do on a given morning*, and what "done" means for each piece of it.

---

## How to read this file

Each task follows the same shape, because the shape is the point:

> **T-x.y — Name**
> **Why** — the reason this exists. A task whose why cannot be written in one
> sentence is usually two tasks, or none.
> **Blocked by** — what must be true first.
> **Done when** — the evidence. Not "the code is written."

Three levels, and no more. Anything that needs a fourth level is a task in
disguise; promote it.

| Level | Form | Example |
|-------|------|---------|
| Task | `T-2.3` | Build the AI Gateway |
| Subtask | `T-2.3.1` | Define the provider-neutral interface |
| Step | `a.` `b.` `c.` | Write the `complete()` signature |

### Status

| Mark | Meaning |
|------|---------|
| `[x]` | Done, evidence exists |
| `[~]` | Partly done — the line states exactly what remains |
| `[ ]` | Not started |
| `[!]` | **Blocked on a human decision or an external account** — not on engineering |

`[!]` is deliberately distinct from `[ ]`. Confusing "nobody has done this" with
"nobody *can* do this" is how a plan quietly stops describing reality.

### Sizing

`S` under a day · `M` two to four days · `L` a week or more · `?` genuinely
unknown until the one before it lands. Estimates on Phase 7+ are `?` by default
and honest about it — anything else would be arithmetic dressed as planning.

---

## Right now — the ordered next ten

If you only read one section, read this one. Ordered by what unblocks the most.

| # | Task | Size | Why it is first |
|---|------|------|-----------------|
| ~~1~~ | ~~[T-0.11](#t-011--patch-the-nextjs-vulnerability) Patch Next.js CVE-2025-66478~~ | S | **Done** — audit clean, CI gate and Dependabot added |
| ~~2~~ | ~~[T-2.1](#t-21--close-the-seasonality-gap) Close the seasonality gap~~ | M | **Done** — gate cleared, [ADR Seasonality](adr/Seasonality.md) |
| ~~3~~ | ~~[T-2.3](#t-23--ai-gateway) AI Gateway~~ | L | **Done** — vendor-neutral, schema-validated, injection-tested, accounted |
| ~~4~~ | ~~[T-2.4](#t-24--reasoning-and-hypotheses) Reasoning and hypotheses~~ | L | **Done** — cited, verified, suppression counted, chain time-ordered |
| ~~5~~ | ~~[T-2.5](#t-25--smriti--memory) Smriti — memory~~ | L | **Done** — hybrid, tenant-isolated, outcomes carried. **Phase 2 engineering complete** |
| 1 | [T-0.9](#t-09--aws-account-foundation) AWS account foundation | M | `[!]` Blocks four Phase 0 items and every deployment task |
| 4 | [T-0.8](#t-08--ship-the-frontend) Deploy the frontend | S | `[!]` Makes the work visible; needed for the demo |
| 5 | [T-3.2](#t-32--real-executors) Real executors | L | **Hard gate.** Blocks Phase 10 and the killer demo |
| 6 | [T-0.10](#t-010--name-and-logo-clearance) Name and logo clearance | M | `[!]` Gates every public activity, including the paper |
| 7 | [T-0.12](#t-012--vector-redraw-of-the-mark) Vector redraw of the mark | S | Removes four constraints from BRAND.md at once |

**One hard gate remains: #6.** Slipping anything else costs time. Slipping that
one corrupts results downstream — an agent tested against executors that do not
exist. The Phase 9 gate cleared with T-2.1.

**Note on T-2.1.** It closed by contradicting its own plan. The task said "change
the default strategy"; the measurement said the default should stay and the real
bug was the opposite of the reported one. That is the process working — but it is
worth remembering that the misleading number sat in the roadmap for weeks looking
like a fact, because it was precise. Precision is not evidence.

---

# Phase 0 — Foundation

Engineering here is complete. What remains needs an account, a credential, or a
decision that is not yours to make in code.

## T-0.8 — Ship the frontend

**Why** — work nobody can see gets re-litigated instead of reviewed.
**Blocked by** — a connected Vercel account, and the API reachable at a public URL.
**Done when** — the dashboard loads at a public URL and `/health` reports through it.

- `[!]` **T-0.8.1 — Connect Vercel** · S
  - a. Create the project against this repo, root directory `apps/web`
  - b. Set `NEXT_PUBLIC_API_URL` per environment
  - c. Confirm preview deployments build on pull requests
- `[!]` **T-0.8.2 — Expose the API** · M
  - a. Public HTTPS endpoint for `services/api`, reachable from Vercel
  - b. CORS restricted to the deployed origins — **not** `*`
  - c. Confirm the frontend never reaches a database directly, per [DEPLOYMENT.md](DEPLOYMENT.md)
- `[ ]` **T-0.8.3 — Verify the chrome under real conditions** · S
  - a. Execution mode indicator shows `dry run` on the deployed build
  - b. API-unreachable state renders correctly — kill the API and look
  - c. Light and dark themes both correct on first paint, no flash

## T-0.9 — AWS account foundation

**Why** — four Phase 0 items and every later deployment task queue behind this
one credential.
**Blocked by** — `aws configure sso`. Tooling is installed; only access is missing.
**Done when** — `terraform apply` provisions the RDS instance into a real account.

- `[!]` **T-0.9.1 — Account structure** · M
  - a. Separate dev, staging, prod accounts under one organization
  - b. Identity Center with MFA enforced on every human principal
  - c. Root account locked down, hardware MFA, no access keys — no exceptions
- `[!]` **T-0.9.2 — Audit and cost floor** · S
  - a. CloudTrail on in all accounts, logs to a dedicated account
  - b. Budget alarms **before** the first workload, not after the first bill
  - c. Cost allocation tags matching the Terraform tagging scheme
- `[!]` **T-0.9.3 — Terraform state backend** · S
  - a. S3 bucket, versioned and encrypted
  - b. Lock table
  - c. Backend config per environment, from the existing `.hcl.example`
- `[!]` **T-0.9.4 — Apply the database** · M
  - a. `terraform plan` reviewed line by line — the first apply is the one to read
  - b. Apply to dev; confirm Multi-AZ, encryption, private subnets, deletion protection
  - c. Confirm the generated password landed in Secrets Manager and appears in no state output
  - d. Run the migrations against it; confirm the append-only triggers actually fire

## T-0.10 — Name and logo clearance

**Why** — this gates all public activity: launch, incorporation, the paper's
title page, the domain portfolio.
**Blocked by** — a legal and commercial decision.
**Done when** — a written go/no-go exists as an ADR.

- `[!]` **T-0.10.1 — The name** · M
  - a. USPTO search in the relevant classes, not just an exact-string search
  - b. State corporate-name availability
  - c. Domains — `.com`, `.ai`, `.dev`. Availability is not clearance
  - d. GitHub org, LinkedIn, social handles reserved
- `[!]` **T-0.10.2 — The logo** · S
  - a. Establish the artwork's origin and licence. It arrived with neither
  - b. If rights are not clear, commission an original mark. Cheaper now than after a launch
  - c. Confirm the final mark is registrable — a logo you cannot register is a logo you cannot defend
- `[ ]` **T-0.10.3 — Record the decision** · S
  - a. ADR covering name, mark, and their clearance basis
  - b. If it is no-go, the ADR says what the fallback name is

## T-0.11 — Patch the Next.js vulnerability

**Why** — `apps/web` is pinned to `next@15.1.6`, which npm flags for
**CVE-2025-66478**. A security platform shipping a known-vulnerable frontend is a
credibility problem before it is a technical one, and it is the first thing a
security-minded buyer will check.
**Blocked by** — nothing. Do this today.
**Done when** — `npm audit` is clean for this advisory and the build passes.

- `[ ]` **T-0.11.1 — Upgrade** · S
  - a. Read the advisory and the patched-version range
  - b. Bump `next` in `apps/web/package.json`; refresh the lockfile
  - c. `npx tsc --noEmit` and `npm run build` both pass
  - d. Check the App Router surfaces the app uses — layout, error, not-found, loading — still behave
- `[ ]` **T-0.11.2 — Make this recurring, not heroic** · S
  - a. Add dependency audit to the CI workflow alongside the existing gitleaks gate
  - b. Decide the severity threshold that fails a build, and write it down
  - c. Enable automated dependency PRs so the next one arrives as a diff, not a discovery

## T-0.12 — Vector redraw of the mark

**Why** — the current logo is 176×176 raster. That single fact produces every
constraint in [BRAND.md](BRAND.md): unusable above ~176px, unthemeable,
unanimatable. A redraw removes all of them at once.
**Blocked by** — T-0.10.2. Do not invest in redrawing artwork that may not be usable.
**Done when** — an SVG renders identically at 24px and at 2000px.

- `[ ]` **T-0.12.1 — Redraw** · M
  - a. Vector redraw at full detail
  - b. A simplified variant that survives 16–24px, where fine detail becomes mud
  - c. Both themes checked on `--ground` and on white
- `[ ]` **T-0.12.2 — Resolve the colour collision** · S
  - a. The mark's crimson sits near `--crit`, which means critical severity everywhere else
  - b. Either shift the mark's red away from `--crit`, or keep the mark permanently out of status regions — pick one and record it
  - c. Confirm no screen places the mark beside a severity badge
- `[ ]` **T-0.12.3 — Clean up** · S
  - a. Replace `logo.webp` and `app/icon.webp`
  - b. Delete `mark.svg` and `logo.svg` — two unused marks in a repo is an invitation to use the wrong one
  - c. Generate the favicon and social preview sizes

## T-0.7 — Threat model review

- `[!]` **T-0.7.1 — Second reader** · S — *the only remaining Phase 0.7 item*
  - a. A reader who did not write it. Self-review of a threat model finds what you already thought of
  - b. Focus on the trust boundaries, which is where threat models usually fail
  - c. Record findings as issues, not as comments in the document

---

# Phase 1 — Drishti · Perception

**Complete**, and the exit criterion is met. Two follow-ups only.

- `[!]` **T-1.1 — Live-verify the CloudTrail connector** · S — normalization is
  tested, but it has never seen a real trail. Blocked by T-0.9
- `[ ]` **T-1.2 — Wire one-click approve to execution** · S — deferred to
  [T-3.4](#t-34--approval-ux) by design, since it needs real executors

---

# Phase 2 — Buddhi + Smriti · Intelligence

The current frontier. Detection and correlation are built; grounding, reasoning
and memory are not.

## T-2.1 — Close the seasonality gap

**Why** — **this is a hard gate.** The shipped robust-z default scores **859
false alarms per 1000** on a daily-shaped series where EWMA scores **43**. Nearly
every signal worth watching is daily-shaped, because human activity is. A
detector that fires every weekday morning trains operators to ignore it, and an
ignored detector is worse than an absent one — it produces the appearance of
coverage. Phase 9 security detection inherits this baseline, which is why it
cannot start first.
**Blocked by** — nothing. The evaluation harness already exists.
**Done when** — the default strategy scores within a stated tolerance of the best
candidate on daily-shaped series, and the choice is recorded with its numbers.

- `[x]` **T-2.1.1 — Reproduce and characterise** · S
  - a. Reproduced: 901/1000 on the square fixture. **But 0/1000 on a realistic sine** — the headline number was a fixture artifact
  - b. Phase breakdown: the square-wave alarms land on peak (87) and falling (95), not the transitions
  - c. Seasonality and trend both trip it, and so do drift and random walks — one broken assumption, not four bugs
- `[x]` **T-2.1.2 — Choose on evidence** · M
  - a. Scored all candidates on six shapes: flat, flat+outage, square, sine, sine+spike, seasonal+trend
  - b. Added `SeasonalRobustZ` — the existing three did not cover it; seasonal-naive echoes each incident one period later
  - c. Scored on sensitivity as well, which is what exposed the blindness. False alarms alone would have selected *for* it
  - d. Warm-up measured and it is decisive: 3 cycles, 884 samples at period 288, enough to swallow a real outage
- `[x]` **T-2.1.3 — Ship the decision** · S
  - a. **Default unchanged** — the opposite of what this line originally said, because a wrong period fails silently. Recorded with the numbers that forced the change of plan
  - b. [ADR Seasonality](adr/Seasonality.md), matching how the graph decision was made
  - c. Full suite green — 95 core, 133 connectors, 26 api
  - d. Roadmap ticked in the same change; `benchdetect.py --strict` added to CI so the result cannot silently regress
- `[x]` **T-2.1.4 — Report what we chose not to fix** · M — mis-specification is
  measured and surfaced (`unmodelled` beside `warm`), so seasonal metrics left on
  robust-z are visibly blind rather than quietly reporting `NORMAL`
- `[ ]` **T-2.1.5 — Period detection by autocorrelation** · M — *(Phase 5)* makes
  the opt-in automatic. Deferred deliberately: it needs labelled scenarios to
  validate against, and shipping it on judgement is how the original gap happened

## T-2.2 — Correlation tuning

**Why** — the correlation window is currently set by judgement. Phase 5 was
always meant to replace that with measurement.
**Blocked by** — T-2.1 (changing the detector changes what correlation receives)
and the Phase 5 scenario library.
**Done when** — the window is chosen by benchmark, with merge and split rates reported separately.

- `[x]` **T-2.2.0 — Pin the behaviour before tuning it** · S — SC-0002 in the
  labelled corpus: two unrelated services degrading in the same minute must stay
  two incidents. Merges and splits already reported separately by
  `measure_merges`. Currently 0 incorrect merges
- `[ ]` **T-2.2.1 — Sweep the window** · M — *(needs a corpus large enough to
  tune against; 8 scenarios pin behaviour but cannot settle a threshold)*
  - a. Sweep across the scenario library
  - b. Report incorrect merges and incorrect splits **separately** — they are not equally bad, and a combined figure hides which one you are trading
  - c. Report compression ratio beside the merge rate, since compression is trivially maximised by merging everything
- `[ ]` **T-2.2.2 — Sweep adjacency depth** · S
  - a. Find where "related" stops meaning anything, as everything reaches everything
  - b. Confirm the bound is enforced, not advisory

## T-2.3 — AI Gateway

**Why** — every model-touching task after this one depends on it, and rule 5 in
[CLAUDE.md](../CLAUDE.md) forbids engine code from calling a provider SDK
directly. Build the boundary before there is anything to retrofit — the same
argument that put Dharma before Astra.
**Blocked by** — nothing.
**Done when** — two providers are swappable by configuration, with no engine change.

- `[x]` **T-2.3.1 — The interface** · M
  - a. `Provider` protocol in `packages/core/pashupatastra/gateway.py` — model, schema, evidence, budget
  - b. Bedrock (Mantle client) primary; direct API behind the identical shape, sharing one request builder so the two cannot drift
  - c. Chosen by configuration — *evidence: two CI gates, one asserting core imports no model SDK, one asserting nothing outside `providers/` does*
  - d. Retry with backoff and a circuit breaker; a schema violation deliberately does not trip it
- `[x]` **T-2.3.2 — Structured outputs only** · M
  - a. Closed schema registry; every call names one and gets a validated object
  - b. `SchemaViolation` is typed — refusals and truncation included, since both would otherwise be read as content
  - c. Bounded retry, then fail honestly
  - d. **No free-text path exists** — asserted by test, not convention
- `[x]` **T-2.3.3 — Injection defence** · M
  - a. Instructions and evidence are separate fields that cannot be concatenated by accident; evidence is fenced and provenance-labelled
  - b. 6-case adversarial corpus — direct override, fake system turn, fence escape, fence lookalike, tag escape, fake dialogue
  - c. Hostile content cannot escape its block **and cannot suppress its own ingestion** — the second property matters more: text that could delete itself would let an attacker blind the detector by writing a string into a log
  - d. Structured outputs remain the load-bearing part; the fencing is defence in depth
- `[x]` **T-2.3.4 — Accounting** · S
  - a. Attributed per incident, agent and purpose
  - b. Ceiling checked **before** each call — after the spend it is a report, not a limit
  - c. Cost per investigation reportable from the first call
- `[x]` **T-2.3.5 — Evaluation harness** · M
  - a. 4 regression cases run end to end on every change
  - b. Deterministic stub provider — same input, same output, so a regression is attributable to the change that caused it
  - c. Cases pin the *assembled request*, not the model's wording: a prompt or schema edit is a visible diff, and a model's phrasing cannot fail the build
  - d. The stub invents nothing — a stub that fabricates findings makes a demo look like a working system
- `[ ]` **T-2.3.6 — Cache-aware assembly** · M — stable prefix first, so multi-turn
  investigations stop paying full price. Deferred deliberately: the win is
  measurable only against real traffic, and guessing the stable prefix now would
  bake in an ordering we would have to unpick later

## T-2.4 — Reasoning and hypotheses

**Why** — the first output a user would call intelligence, and the first place
the system can be confidently wrong in a way that reads as authoritative.
**Blocked by** — T-2.3.
**Done when** — top-1 root cause is correct ≥70% on 20 labelled incidents, every
hypothesis citing its telemetry.

- `[x]` **T-2.4.1 — Generation** · L
  - a. Hypotheses with confidence and mandatory citations, ranked, bounded to 5
  - b. Reused the core `Hypothesis` validator rather than re-implementing it
  - c. **Added what the validator cannot do: citation *verification*.** The schema checks a ref is present; admission checks it exists in this incident's events. The set shown to the model and the set checked against are the same object — if they ever diverged, verification would silently start passing what it should reject
  - d. Confidence clamped, not rejected — a value of 1.4 is a formatting error, not grounds to discard a well-cited claim, but it must not reach a risk score unclamped
- `[x]` **T-2.4.2 — Suppression** · M
  - a. Unsupported hypotheses suppressed, not surfaced at low confidence
  - b. Counted and attributable by reason, with a suppression rate — silent suppression is its own failure mode
  - c. Duplicates dropped: repetition reads as corroboration
- `[x]` **T-2.4.3 — Contradiction** · M
  - a. `contradicted_by` populated and preserved
  - b. A fabricated counter-ref is filtered *without* killing the hypothesis — the asymmetry matters, since rejecting the whole claim would let a fabrication suppress a well-supported finding
  - c. *(UI rendering follows in the console work)*
- `[x]` **T-2.4.4 — Change correlation** · M
  - a. Deterministic — no model. "Did something change just before this broke?" is a question about timestamps, and answering it with a model would be slower, costlier and less reliable than a comparison
  - b. Deploys after onset excluded; offering them invites the post-hoc reasoning this prevents
  - c. Offered as citable evidence with its timing spelled out, never as a verdict
- `[x]` **T-2.4.5 — Causal chain** · M
  - a. Links assembled, each citing its events
  - b. Ordered by observation time, not the model's narrative — when the two disagree, the timestamps are right
  - c. Built from admitted hypotheses only, so a suppressed top hypothesis leaves no chain behind
- `[x]` **T-2.4.6 — Measure the exit criterion** · S — top-1 accuracy,
  precision-when-answering and grounding reported separately. Abstentions count
  against accuracy (a system that declines everything is unused, not perfect);
  the match rule is a parameter, since hard-coding a weak equivalence test would
  quietly cap the measured accuracy of every later improvement
- `[~]` **T-2.4.7 — Run against 20 labelled incidents** · M — corpus now exists
  (8 scenarios, `benchmark/incidents/`), but **two gaps remain and neither is
  closable here**: it is 8 rather than 20, and reasoning quality needs a real
  model. Scoring top-1 accuracy against the deterministic stub would measure a
  fixture this repo wrote, so the number is absent rather than reported.
  Detection, correlation and recall are genuinely scored and pass 8/8

## T-2.5 — Smriti — memory

**Why** — "have we seen this before" is the question an experienced operator asks
first and a new system cannot answer at all.
**Blocked by** — T-2.3 for embeddings.
**Done when** — a recurring incident retrieves its prior occurrence and outcome.

- `[x]` **T-2.5.1 — Storage** · M
  - a. Incident embedding and storage; local lexical embedder so core still runs on a laptop
  - b. Tenant isolation structural — required positional argument, no cross-tenant read path, unknown tenant returns empty rather than erroring (an error is an enumeration oracle)
  - c. Source, timestamp, confidence, owner, retention all carried; retention enforced on read so a stalled pruning job cannot resurface an expired memory
- `[x]` **T-2.5.2 — Retrieval** · L
  - a. Hybrid, recorded as [ADR Smriti](adr/Smriti.md)
  - b. **The basis is reported, not blended.** Ranking happens within a basis, so a strong text-only match cannot outrank a weak same-entity one — a single relevance score would let a coincidence of phrasing win on a good enough embedding
  - c. Asymmetric floors: text-only must clear a similarity threshold, structural need not. Filter-then-rank loses the same-service-different-wording case, which is often the most useful one
  - d. `score_retrieval` measures it, with `false_precedents` reported separately and a negative case (without which a retriever returning everything scores perfectly)
- `[x]` **T-2.5.3 — Surfacing** · M
  - a. "We have seen this before" — only for `same_entity` / `same_signal`; a text-only resemblance is labelled as not a precedent, to the model as well as the UI
  - b. The outcome travels with it. Wrong diagnosis, failed verification and never-resolved each produce a `CAUTION`, injected into the evidence the model reads
  - c. An unmatched query returns nothing; nothing manufactures a precedent to avoid an empty result
- `[x]` **T-2.5.4 — Ingest written knowledge** · M
  - a. Runbooks and architecture decisions ingested
  - b. Always untrusted — **there is no `trust=` parameter**, because a parameter is what someone passes `VERIFIED` to while wiring up an importer
  - c. `promote()` requires a named actor and records them as owner
- `[x]` **T-2.5.5 — Wire memory into reasoning** · M — precedents become citable
  evidence, so a recollection is a verifiable reference rather than a hint the
  model half-remembers. An incident cannot recall itself, or it cites its own guess
- `[ ]` **T-2.5.6 — Adopt a hosted embedder on evidence** · M — the local embedder
  is lexical and will miss semantically-similar incidents that share no
  vocabulary. A real recall gap, accepted knowingly; the upgrade should be argued
  with `score_retrieval` numbers the way the graph store was

---

# Phase 3 — Astra + Dharma · Action

Policy, guarded execution and audit exist. What is missing is anything real
behind them.

## T-3.2 — Real executors

**Why** — **the second hard gate.** The registry guard is compile-time; a
rollback that has never run is a rollback you do not have. Phase 10 containment
and the killer demo both queue behind this.
**Done when** — every action has a rollback that has been executed and verified.

- `[x]` **T-3.2.1 — Kubernetes executor** · L
  - a. Restart, scale, rollback, redeploy, halt — all five, via `kubectl`
  - b. Post-state and rollback already enforced at registration; parameters validated before any call, since `kubectl` with no namespace silently targets `default`
  - c. **Verified live** against kind / Kubernetes v1.36.1 — `scripts/verifyexecutors.py`, 11 checks, all passing. It found two bugs the mocked tests could not: the rollback ran with the original parameters, and `restart_service` declares itself as its own rollback. Both fixed; see T-3.2.5
- `[~]` **T-3.2.2 — Supporting executors** · M
  - a. *(Cache flush/warm not built — registered and deniable, but no executor performs them. An unowned action fails loudly rather than appearing to succeed, and a test pins exactly which actions are declarable-but-not-performable)*
  - b. Ticketing and notification built. Escalation is a registered action, not application code — otherwise it is not audited, not measured, and not selectable by policy
- `[x]` **T-3.2.3 — Rollback under failure** · L
  - a. Every registered rollback walked at runtime and asserted to resolve *and* complete; a second test asserts each is performable by some executor, which the registry cannot see
  - b. Degraded-system paths covered: execution error, verification failure, unobservable post-state, and an observer that throws — each routes to rollback rather than to a guess
  - c. Rollback-fails-too is a first-class `ROLLBACK_FAILED` state that pages in prose. An *unverified* rollback counts as failed, since an undo that cannot be shown to have worked is indistinguishable from none
  - d. The loop never retries the original action and never retries the rollback — bounded, then a human
- `[x]` **T-3.2.4 — Live opt-in** · S
  - a. **Two independent gates**, both required: `dry_run: false` and the environment listed in `live_environments` (empty by default). One flag is one accident away from a production write
  - b. Every gate can veto, none can override — a per-verdict constraint can force dry-run but never grant live execution, so misconfiguration fails closed
  - c. The live executor is constructed lazily, so a process not permitted to write never holds a configured cluster client
  - d. *(Chrome already shows execution mode; confirming it against a live run is part of the console work)*
- `[x]` **T-3.2.5 — What the live run changed** · M
  - a. **Rollback now restores captured prior state**, not the original params. A `capture` step snapshots before acting; on the cluster this is the difference between `scale_service(replicas=2)` and `scale_service(replicas=4)` as the "undo"
  - b. If the snapshot fails, the loop **refuses to act at all** — not acting costs an escalation, acting blind costs an unrecoverable change
  - c. **A self-rollback with nothing to restore escalates** rather than repeating the action. Kubernetes rejecting two restarts in one second is what exposed it, reported as a `ROLLBACK_FAILED` page for a state that was never broken
- `[ ]` **T-3.2.6 — Resolve the self-rollback registry entries** · M — `restart_service`
  and `modify_db_config` declare themselves as their rollback while undoing
  nothing. Pinned by a test rather than quietly patched: deciding what the
  rollback of a restart *should* be is a policy question, and the binary
  rollback-or-irreversible model cannot currently express "low risk,
  self-healing, not undoable"

## T-3.3 — Agent runtime

- `[x]` **T-3.3.1 — Load and enforce declarations** · L
  - a. Allow-list consulted on **every call** — proven by mutating the declaration after construction and watching the next call still be refused
  - b. Undeclared tools are unreachable *and* never held; denied attempts are recorded rather than dropped, since a repeatedly-refused tool is a signal about the declaration or the prompt
- `[x]` **T-3.3.2 — Budgets** · M
  - a. Tokens, actions and wall clock, all checked **before** the spend
  - b. Exhaustion escalates. A refused action does not spend the action budget — charging for a refusal makes the budget punish caution
- `[x]` **T-3.3.3 — Escalation** · M
  - a. Reason and detail recorded; the first escalation wins, because the first reason is the true one
  - b. First-class outcome throughout — the runtime never treats a hand-off as an error
- `[x]` **T-3.3.4 — Sati, the first roles** · L
  - a. One identity, four roles, one runtime
  - b. `sati.orchestrator` (risk 0 — it routes, never acts), `sati.incident`, `sati.infrastructure`, `sati.security` (read-only *by declaration*, and budgeted to zero actions)
  - c. Each with its own tools, budget and ceiling; a test asserts the tool sets genuinely differ, since four identical specs would satisfy least-privilege in form and none of its intent
  - d. Dev-only, pinned by test — widening production authority should be a visible diff
- `[x]` **T-3.3.5 — Verify the fleet live** · M — `sati.infrastructure` scaled a
  real deployment through the runtime, was refused an undeclared tool, and had a
  risk-65 action denied against its ceiling of 45. Declared limits are only
  limits if something enforces them against a system that can actually change

## T-3.4 — Approval UX

**Why** — the approval surface already shows the full risk arithmetic. What it
lacks is the ability to act, and a way to know whether approval means anything.

- `[~]` **T-3.4.1 — Wire the button** · M
  - a. `POST /policy/approve` records the approver; `POST /policy/deny` added
  - b. Denial returns 200 with the refusal recorded — an HTTP error would make "a human said yes" the client's success path
  - c. Expiry surfaced as a 409 at click time, not discovered later by `is_executable`
  - d. **Still owed: binding the web button.** The surface renders the full risk arithmetic; the click is not yet wired to the endpoint
- `[x]` **T-3.4.2 — Measure approval fatigue** · M
  - a. Time-to-decide and approval rate tracked, timed from **presentation** so queueing is not counted as deliberation
  - b. `looks_decorative` requires *both* halves — near-total approval **and** near-instant decisions. Each is innocent alone, and tests pin that: a deliberated 100% approval rate is a system working, and fast decisions with real denials mean someone is deciding
  - c. Summary leads with the uncomfortable number; `None` below 10 decisions rather than a reassuring `False`; per-approver breakdown so one rushed person is visible behind a healthy average
- `[ ]` **T-3.4.3 — Persist approvals** · S — fatigue is per-process today, so a
  restart resets the measurement. Belongs alongside the audit trail in Postgres,
  where the append-only triggers already apply

## T-3.5 — AWS enforcement floor

- `[x]` **T-3.5.1 — IRSA per agent** · M — *was blocked by T-0.9; the code and its
  verification did not need the credential, only the apply does*
  - a. One role per agent, one service account, `sub`-conditioned so no other pod can assume it
  - b. Read and write as separate policies, so no-write means no policy attached
  - c. Destructive actions **denied**, not merely ungranted — explicit Deny wins over any Allow, so the floor cannot be raised by a later grant. Includes `iam:*` and `cloudtrail:StopLogging`
  - d. **The mirror is tested**: 14 tests assert `agents.json` matches `sati_roles()` exactly, so declaration/credential drift fails CI. `terraform plan` verified against the real provider
- `[~]` **T-3.5.2 — Secrets** · S — Secrets Manager holds the database credential,
  generated by Terraform and never in state output. **KMS customer-managed keys
  still owed** — the secret uses the AWS-managed key today
- `[ ]` **T-3.5.3 — Apply it** · S — the plan is verified (11 to add, 0 to change,
  0 to destroy) and nothing is provisioned. Needs a deliberate call: RDS costs money
- `[ ]` **T-3.5.4 — Retire the static access key** · S — the CLI authenticates as
  an IAM user with a long-lived key, which SECURITY.md T9 forbids and
  DEPLOYMENT.md permits only as a bootstrap. Closes when Identity Center exists
  and the key is deleted

---

# Phase 4 — Verification

Contracts and grading exist. Live observation does not.

- `[x]` **T-4.1 — Post-action observation** · L
  - a. `[x]` Observation window against real telemetry — verified on a live kind
    cluster, including real sample pacing, which a fake clock cannot check
  - b. `[x]` Per-action tuning — a restart settles faster than a rollback
  - c. `[x]` Missing observation grades as **failure**, never success. Already true; keep it true
- `[x]` **T-4.2 — Automatic rollback** · L
  - a. `[x]` Roll back on verification failure — now graded over a window, so a
    metric that merely bounces no longer closes the incident
  - b. `[x]` Escalate when rollback itself fails
  - c. `[x]` Never loop — one attempt, one undo, then a human
  - d. `[x]` The undo carries its own Dharma verdict, and a mismatched verdict is
    refused before the loop starts rather than inside the runner
- `[x]` **T-4.3 — Learning** · M
  - a. `[x]` Outcomes to Smriti, **successes and failures with equal prominence** —
    one write path, no success-only branch, same kind and retention either way
  - b. `[x]` Novelty penalty fed by execution history — per environment, with a
    horizon; tried-and-failed now scores above never-tried
  - c. `[x]` Predicted vs actual blast radius tracked — the system's estimation error is a
    metric it should publish about itself. Signed, so under-estimation is visible
    rather than averaged away
- `[x]` **T-4.4 — Timeline UI** · M
  - a. `[x]` Detection → hypothesis → plan → approval → execution → verification —
    six fixed stages, so a stage that never ran is visible rather than absent
  - b. `[x]` Every step linked to its audit record, by anchor to the specific rows
  - c. `[x]` A stage is evidenced by an audit record, a state transition, or the
    artefact it produces — records alone wrongly accused Detection of never running
  - d. `[ ]` No frontend test framework; verified by rendering both paths instead

---

# Phase 5 — PIB · Benchmark

- `[ ]` **T-5.1 — Scenario library** · L
  - a. Schema and validator
  - b. 100+ scenarios across the eight seed categories
  - c. **Negative scenarios** — where the correct answer is to do nothing
  - d. **Escalation scenarios** — where the correct answer is to hand off
  - e. All authored **before** the logic that resolves them
- `[ ]` **T-5.2 — Harness** · L
  - a. Fault injection against the real containerized stack
  - b. Ephemeral environment per run
  - c. N runs per scenario, variance reported
  - d. One-command reproducibility
- `[ ]` **T-5.3 — Arms and ablations** · L — human, runbook automation, naive LLM
  agent, full system; then remove one component at a time
- `[ ]` **T-5.4 — Reporting** · M
  - a. Metrics from the audit log alone, per [research/METRICS.md](research/METRICS.md)
  - b. **False remediation rate before autonomous resolution rate**
  - c. Per-scenario results, not only aggregates; excluded scenarios state why

---

# Phase 6 — Research and release

- `[ ]` **T-6.1 — Paper** · L — draft, results, ablations, threats to validity
  including the self-authored benchmark, failure analysis, preprint
- `[ ]` **T-6.2 — Open source** · L — split the monorepo, licence, contribution
  guide, disclosure process, third-party reproducibility on release day
- `[ ]` **T-6.3 — Launch** · M — website, and the killer demo end to end, unedited

---

# Phases 7–12 — Kavach

Full detail in [KAVACH.md](KAVACH.md). Task-level breakdown is deliberately
shallow here: these depend on decisions that Phases 2–5 have not made yet, and
detailing them now would be invention rather than planning. Expand each phase as
its dependency clears.

| Phase | Headline tasks | Gate |
|-------|---------------|------|
| 7 — Security data | Event model v1 · endpoint, auth, network connectors · CVE/KEV/ATT&CK/MISP intel · intel-as-data enforcement · dataset quality | Phase 1 |
| 8 — Knowledge | Security ontology on the existing `EntityRef` · knowledge graph on the Phase 1 store · the five queries · ATT&CK chain and coverage gaps | Phase 7 |
| 9 — Detection and grounding | Security detectors on the existing harness · kill-chain correlation · RAG with enforced citation · Smriti security memory with tenant isolation | **T-2.1** |
| 10 — Blue Team agents | `sati.sentinel`, `sati.hunter`, `sati.analyst` · containment under Dharma · evidence trail · automation-bias measurement | **T-3.2** |
| 11 — Cyber range | Isolated instrumented range · controlled adversary emulation · Red vs Blue scoring · negative and escalation scenarios | Phase 5 |
| 12 — Benchmark and studies | PSB · six arms · six ablations · held-out family and temporal splits · human-AI study · paper | Phase 11 |

**The two gates in bold are the ones that matter.** Everything else in this table
can slip without corrupting a result.

---

## Keeping this file honest

Same protocol as the roadmap, and for the same reason:

1. Tick a box **in the change that finished it**, never in a separate pass
2. `[x]` needs evidence — a passing test, an applied migration, a committed
   decision. "The code is written" is not evidence
3. If work lands that no task covers, **add the task and tick it**. The plan
   tracks reality, not the other way around
4. When a `[!]` unblocks, downgrade it to `[ ]` and say what changed
5. When a task turns out to be three tasks, split it. A task that has been
   in progress for three weeks is usually mis-sized, not slow
