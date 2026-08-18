# Plan of Action

**Pashupatastra — 24-week path from empty repository to research release.**

Each phase has a hard exit criterion. A phase is not done when the code is
written; it is done when the criterion is demonstrably met. Phases 1–4 build the
loop in the order the loop runs, so every phase ends with something demonstrable
rather than a half-wired layer.

## How this document is maintained

**This file is the live status of the project, not a historical plan.** Every
task carries a checkbox. When a task is genuinely finished, tick it in the same
change that finished it — never in a separate "update the roadmap" pass, which
is how status drifts from reality.

| Mark | Meaning |
|------|---------|
| `- [x]` | Done, and its evidence exists — tests pass, the file is committed, the criterion is met |
| `- [~]` | Partly done. The line says exactly what remains |
| `- [ ]` | Not started |

A task is ticked only when its **evidence** column is true. "The code is
written" is not evidence; a passing test, an applied migration, or a committed
decision is.

## Schedule

Week 1 begins **Monday 10 August 2026**.

| Phase | Weeks | Dates | Status |
|-------|-------|-------|--------|
| 0 — Foundation | 1–2 | Aug 10 – Aug 23 | **In progress** — everything not needing AWS access or a legal decision is done |
| 1 — Drishti · Perception | 3–6 | Aug 24 – Sep 20 | **Started early** — framework and Prometheus connector done |
| 2 — Buddhi + Smriti · Intelligence | 7–10 | Sep 21 – Oct 18 | Not started |
| 3 — Astra + Dharma · Action | 11–14 | Oct 19 – Nov 15 | Partly built early |
| 4 — Verification | 15–17 | Nov 16 – Dec 6 | Partly built early |
| 5 — PIB · Benchmark | 18–20 | Dec 7 – Dec 27 | Not started |
| 6 — Research & OSS release | 21–24 | Dec 28 – Jan 24 2027 | Not started |

### Why Phases 3 and 4 are partly built already

The policy engine, the guarded execution path, and expected-state verification
were written during Phase 0 rather than deferred. Deliberate, not scope creep:
had Astra been built first and Dharma retrofitted, the verdict argument would
have been optional in practice, and every execution path added later would have
been somewhere to forget it. Building the constraint first makes it structural.

What remains in those phases is the part that needs Phases 1 and 2 to exist —
real connectors behind the executors, the agent runtime, approval UX, IRSA
roles, and verification against live telemetry rather than supplied values.

---

## Phase 0 — Foundation · Weeks 1–2 · Aug 10 – Aug 23

**Goal:** every constraint that governs the system is written down before code
can violate it.

### 0.1 Repository and documentation

- [x] Repository scaffold, `README.md`, `CLAUDE.md` — *evidence: committed*
- [x] `docs/ARCHITECTURE.md` — subsystems, data flow, non-goals
- [x] `docs/REPOSITORY.md` — directory purpose and import discipline
- [x] `docs/GLOSSARY.md` — every term defined once
- [x] `docs/CONTRIBUTING.md` — workflow, commits, review bar
- [x] `.claude/memory/` protocol — template, index, entries
- [x] Documentation index with every file reachable — *evidence: link checker passes*

### 0.2 Decisions of record

- [x] ADR **Monorepo** — one repo until the open-source split
- [x] ADR **Grounding** — the LLM is not the source of truth
- [x] ADR **Observability** — sit above existing tooling, never replace it
- [x] ADR **Platform** — AWS target, `packages/core` cloud-free
- [x] ADR **Schema** — versioning policy, additive vs. breaking, `v0` grace period
- [x] ADR **Graph** — decision criteria recorded; the decision itself is due in Phase 1, on measurements rather than instinct

### 0.3 Core domain model

- [x] Normalized event model — 8 event classes, typed payloads, mandatory provenance — *evidence: round-trip tests*
- [x] `EntityRef` namespace shared between events and topology
- [x] Quarantine path for unresolvable entities *(held and visible, never dropped)*
- [x] Incident model — lifecycle, transitions, impact, plan, verification
- [x] Hypothesis evidence rule — evidence-free hypotheses fail validation
- [x] Topology graph — blast radius and the adjacency gate for correlation
- [x] Action registry — closed set, each declaring risk, post-state, rollback
- [x] Registry guard — an action with no rollback cannot register above risk 0
- [x] `packages/core` has zero AWS imports — *evidence: CI grep gate*
- [x] 25 tests passing

### 0.4 Policy engine (Dharma)

- [x] Risk scoring with context adjustment — blast radius, environment, confidence, novelty
- [x] Adjustments can only raise risk, never lower it — *evidence: test*
- [x] Autonomy tiers 0–30 / 31–60 / 61–80 / 81+
- [x] Hard overrides — irreversible denied, no-rollback escalated, blast-radius escalation
- [x] Agent risk ceilings enforced above approval
- [x] Expiring verdicts — a stale approval cannot be replayed
- [x] `require_verdict` guard on the single execution path
- [x] Denial test for every tier — *evidence: 12 policy tests*

### 0.5 API service

- [x] FastAPI app, config via environment, dry-run default
- [x] Policy evaluate / approve endpoints
- [x] Guarded execution endpoint
- [x] Verification endpoint with threshold grading
- [x] Append-only audit log, written **before** execution
- [x] Engine-level bypass proven impossible — *evidence: test, not just HTTP-level*
- [x] 14 tests passing
- [x] OpenAPI specification exported to `openapi.json` and pinned — *evidence: CI fails when the surface drifts*
- [x] Postgres schema and migrations — *evidence: migrations apply clean, 11 persistence tests pass*
- [x] Append-only enforced by triggers, not convention — *evidence: UPDATE/DELETE on audit raises*
- [x] `execution.verdict_id` NOT NULL — an unauthorized execution is unwritable at the SQL layer
- [x] Immutable migrations — an applied file that later changes is an error
- [x] API reads and writes Postgres — *evidence: `/health` reports `audit_storage: postgres`, rows persist across processes*

### 0.6 Agent specification

- [x] `AgentSpec` model — identity, permissions, tools, memory, budget, risk limit
- [x] YAML loader and validator
- [x] Example declaration — `services/api/app/policies/databaseresponder.yaml`
- [x] Least-privilege proven — undeclared tools unreachable, environment promotion explicit — *evidence: tests*
- [x] Budget ledger with enforced exhaustion
- [ ] Agent runtime that consumes the declaration *(Phase 3 — needs connectors first)*

### 0.7 Security

- [x] Threat model — 9 threats with controls, trust boundaries
- [x] Non-negotiable controls documented
- [~] AWS credential handling — the *design* is no long-lived keys (SSO for humans, IRSA for workloads, OIDC for CI), and that is what `agents.tf` builds. **But the CLI is currently authenticated as an IAM user with a static access key** (`arn:aws:iam::…:user/Claude`), which is the documented bootstrap fallback in [DEPLOYMENT.md](DEPLOYMENT.md) and *not* the target state. Un-ticked deliberately: [SECURITY.md](SECURITY.md) T9 says "nothing static", and leaving this marked done would make the control read as satisfied when it is not. Closes when Identity Center exists and the key is deleted
- [x] `.gitignore` covers `.env`, keys, `*.tfstate`
- [x] Secret scanning in CI — gitleaks
- [ ] Threat model reviewed by a second person — **blocked: needs a human reviewer**

### 0.8 Frontend foundation

- [x] Next.js app, TypeScript strict, Tailwind
- [x] Design tokens — restrained palette, no mythological ornament
- [x] Logo and `docs/BRAND.md`
- [~] Mark — the illustrated spear artwork is wired into the header and favicon and the build passes. **Owed: a vector redraw.** The source is 176×176 raster, too small for hero or print, and its crimson sits close to `--crit`, which means critical severity everywhere else in the interface
- [x] ~~Geometric mark — loop, shaft, decision node, trident head~~ — *superseded 17 Aug 2026 by the owner's decision to use the artwork; `mark.svg` and `logo.svg` retained but unused*
- [x] Overview, incident detail, action registry pages
- [x] Causal chain renders evidence citations per link
- [x] Dashboard computes no risk itself — renders API answers only
- [x] Typecheck and production build pass
- [ ] Deployed to Vercel with the API reachable — **blocked: needs a Vercel account connected**

### 0.9 Infrastructure

- [x] `docker-compose` reference stack — Postgres, Redis, OpenSearch, Prometheus, Grafana, MinIO
- [x] Every managed service has a self-hosted counterpart — *evidence: mapping table in DEPLOYMENT.md*
- [x] Terraform skeleton — providers, variables, backend, tagging
- [x] RDS PostgreSQL module — Multi-AZ in prod, encrypted, private, deletion-protected, password generated into Secrets Manager — *evidence: `terraform validate` passes*
- [x] AWS CLI and Terraform installed locally
- [x] Per-environment tfvars and backend config
- [x] CI — core, api, web, secret scan, cloud-free gate
- [ ] AWS account structure — dev/staging/prod separation, Identity Center, MFA enforced, root locked down — **blocked: needs `aws configure sso`**
- [ ] CloudTrail enabled in all accounts, budget alarms set — **blocked: same**
- [ ] Terraform state backend provisioned (S3 + lock table) — **blocked: same**
- [ ] `terraform apply` the RDS instance — **blocked: same**

### 0.10 Name clearance — **blocker**

- [ ] USPTO trademark search
- [ ] State corporate-name availability
- [ ] Domains — `.com`, `.ai`, `.dev`
- [ ] GitHub organization, LinkedIn page, social handles
- [ ] **Logo provenance and licensing established** — the artwork now used as the
      mark arrived without a stated source or licence. A logo cannot be
      registered, and should not be commercialised, without clear rights to it.
      This belongs in the same clearance pass as the name, and carries the same
      consequence if skipped
- [ ] Written go/no-go decision recorded as an ADR

**This gates all public activity.** Build under the name; do not launch,
incorporate, or buy a domain portfolio until it clears. A domain being available
is not evidence the trademark is — and artwork being in hand is not evidence it
is yours to use.

**Phase 0 exit criterion:** every constraint documented, core and policy tested,
name decision recorded.

### What is left, and why

Everything buildable from this machine is done. The remainder needs something
only you can supply:

| Remaining | Needs |
|-----------|-------|
| AWS accounts, CloudTrail, budget alarms, state backend, **RDS apply** | An authenticated AWS CLI profile. Tooling is installed and the RDS config validates; only credentials are missing |
| Vercel deployment | A connected Vercel account, plus the API reachable at a public URL |
| Threat model review | A second human reader |
| Name clearance | A legal/commercial decision, not an engineering one |

No engineering tasks remain open in Phase 0. The API now reads and writes
Postgres and reports `degraded` on `/health` if it ever falls back to memory.

**Risk:** over-specifying schemas before real telemetry exists. Mitigation —
version the event schema from v0 and treat Phase 1 as the first migration test.

---

## Phase 1 — Drishti · Perception · Weeks 3–6 · Aug 24 – Sep 20

**Goal:** heterogeneous telemetry becomes one normalized stream and one live
topology.

### 1.1 Connector framework

- [x] Connector interface — `Connector`, `Window`, `Harvest`; provenance stamped by the connector, not the caller
- [x] Read-only by construction — no connector exposes a mutating method
- [x] Normalization into the core event model, with quarantine on unresolvable entities — *evidence: tests*
- [x] Schema conformance across all seven sources — provenance, entity resolution, tz-aware timestamps, JSON round-trip, and no structure smuggled into `labels`. **v0 survived**; it needed no field the model lacks

### 1.2 Connectors

- [x] Prometheus — 9 tests, including one against a live local instance; AMP differs only by base URL and request signing
- [x] Kubernetes — pods, deployments, services, ownership edges; verified against a live kind cluster. EKS differs only in authentication
- [x] OpenTelemetry — OTLP/HTTP receive endpoint; service hops rebuilt from the span tree, not span ordering, which concurrency makes meaningless
- [x] OpenSearch — error-rate aggregates plus a bounded sample; log text carried verbatim as data, never as instruction — *verified against a live instance with an injection attempt in the corpus*
- [x] CI/CD deployment events — GitHub deployments connector and a webhook receiver; a deployment carries no severity, since 'a deploy happened' must not read as 'a deploy broke something'
- [x] CloudTrail — mutating calls as `state_change`, security-relevant calls as `security`; reads filtered out. *Normalization tested; live verification still needs AWS credentials*
- [x] Docker — container state and restart counts via the CLI rather than the daemon socket, which is root-equivalent and wrong for a read-only connector

**Sequencing:** Prometheus and Kubernetes only until the graph is correct. The
rest are additive and must not be started before the graph is trusted.

### 1.3 Topology graph

- [x] Persistence — **Postgres**, decided by measurement rather than instinct (ADR Graph)
- [x] Graph store with upsert reconciliation — a failed poll cannot empty the graph, because an empty graph reports zero blast radius and silently lowers risk
- [x] Blast-radius traversal in Postgres, **parity-tested** against the core reference on transitivity, direction, depth, cycles, and unknown origins — *evidence: 16 tests*
- [x] p99 **18.3ms** on 4,009 nodes / 10,006 edges against a 200ms target — *evidence: `scripts/benchgraph.py`*
- [x] Estimated-users attribution per node, protected against a connector that cannot see counts zeroing them
- [x] Staleness policy — pruning is dry-run by default and never automatic: deleting a node whose connector merely broke shrinks blast radius, which lowers effective risk, which would grant *more* autonomy precisely because the system had gone blind
- [x] Graph construction from connector output — nodes from any event; edges **only** from observed call paths or platform declarations, never from co-occurrence

### 1.4 Ingestion pipeline

- [x] Ingestion orchestration — **both** paths: pull (poll) and push (receive), converging on one persist-then-reconcile routine
- [x] Events written before the graph, so a mid-cycle crash leaves replayable telemetry
- [x] Failures counted and surfaced — one broken connector degrades perception without stopping the others, and never reads as an all-clear
- [x] Queue-buffered ingestion — bounded FIFO that drops the **oldest**, because under sustained load the newest telemetry is the most diagnostically useful; every drop counted and surfaced
- [x] Retention — Postgres as the hot store, with audit, transitions, verdicts, executions and incidents protected from pruning at runtime; dry-run by default and always audited

### 1.5 Console (UI/UX)

This section was originally two lines — "infrastructure map, service map" — and
the under-specification showed in the product: a working map bolted to a
skeleton. The console is what an operator judges the whole system by at 3am, so
it is scoped properly here rather than left as an afterthought.

**Foundations**

- [x] Design tokens — surfaces, ink, brand, and a **reserved** status palette that never carries a non-status meaning
- [x] Component primitives — one place where status, time, empty states, and identifiers are decided, so an operator does not re-learn the interface on every screen
- [x] Status is never colour-alone: every state ships a glyph and a word
- [x] Tabular figures on all numerals — digits that jitter between refreshes read as unreliable, whatever they say
- [x] Focus-visible treatment on every interactive element, plus a skip link
- [x] `prefers-reduced-motion` respected
- [x] Loading, error, and not-found states — a blank screen mid-incident is indistinguishable from a broken one
- [x] Errors never fall back to cached numbers; a stale figure shown as current is worse than an honest gap
- [x] Bounded lists state their bound — "newest 100 of more", never a silent truncation

**Screens**

- [x] Overview — a verdict sentence first, metrics second, for an operator arriving cold
- [x] Incidents — causal chain with per-link evidence, alternatives with their contradictions, plan with per-action risk
- [x] Infrastructure map — deterministic rank layout, so a node stays put between refreshes and is comparable with what the operator saw ten minutes ago
- [x] Service map with live dependency edges, solid for observed calls and dashed for platform ownership
- [x] Blast-radius API — `/topology/blast-radius/{key}`, served from the graph so there is one answer, not two
- [x] Actions — registry, autonomy tiers, and how effective risk is computed
- [x] Audit — the record every claim rests on, with human and agent actors visually distinct
- [x] Execution mode (dry-run vs live) in the chrome on every page — the most consequential fact about the system, and not something to learn the hard way
- [x] Entity detail — identity, blast radius with links, and recent events with their provenance
- [x] Incident detail as its own route with a shareable URL, sharing one view component with the list so the two cannot drift
- [x] Approval surface — the full risk arithmetic, blast radius, expected post-state and rollback, so an approver can say *why* it needed approving. Answers approval fatigue: a rubber stamp is indistinguishable from no policy at all
- [ ] One-click approve wired to execution *(Phase 3 — needs real executors)*

**Still owed**

- [x] Responsive pass below 640px — nav scrolls rather than wrapping, and execution mode stays visible
- [x] Live updates — 15s poll that pauses when the tab is hidden, states the age of the data, and can be paused mid-read
- [x] Dependency table beside the map — the same data for screen readers, search, and copy-paste
- [x] Light theme with its own status steps — an inverted dark palette fails contrast on white — applied before first paint to avoid a flash

**Exit criterion:** point Pashupatastra at a live 5-service reference stack; the
graph auto-builds within 60s and blast radius for any node is queryable in under
200ms.

**Risk:** connector sprawl eats the phase. Mitigation — the sequencing rule in
1.2 is enforced, not advisory.

---

## Phase 2 — Buddhi + Smriti · Intelligence · Weeks 7–10 · Sep 21 – Oct 18

**Goal:** signals become one incident with a defensible causal chain.

### 2.1 Detection

- [x] Statistical baselines per (entity, metric) — **median and MAD, not mean and stddev**: a sustained outage inflates a mean until the incident teaches the detector it is normal
- [x] Baselines judge *before* they learn, so a value never partially normalizes itself in the act of being measured
- [x] A cold baseline reports **unknown, never normal** — those are different claims, and only one of them closes an incident early
- [x] Confidence scales with sample count as well as deviation, because it feeds effective risk and overstating it would widen what the system may do
- [x] Anomaly detection producing findings that cite the events behind them
- [x] Alert ingestion that **defers** to upstream rules instead of seconding them — two findings for one fact read downstream as corroboration
- [x] Warm-up state is reportable, so an unwarmed detector's silence is not mistaken for an all-clear
- [x] Evaluation harness — one interface for every detector, scored online on labelled series by precision, episode recall, **lead time**, and false alarms per 1000. Makes the ML decision a measurement rather than an argument
- [x] Three statistical candidates to beat: robust-z (incumbent), EWMA, seasonal-naive
- [x] **Seasonality gap — closed, and the diagnosis corrected.** The 859-per-1000 figure came from a *square-wave* fixture; on a realistic sine shape robust-z emits **zero** false alarms. Its true failure is the opposite and worse: seasonal spread inflates MAD until the band (−26…157) is wider than the data (38…102), so it needs a spike near **180** on a series peaking at 100 while the seasonal strategy catches **110**. Blind, not noisy — and blindness reads as an all-clear. *Evidence: [ADR Seasonality](adr/Seasonality.md), `scripts/benchdetect.py`, 8 tests*
- [x] `SeasonalRobustZ` — per-phase median with robust residuals; best on every workload, and free of the echo that pins seasonal-naive's precision at 0.50
- [x] **Kept opt-in rather than made the default**, against the original plan: a *wrong* period makes it blind rather than noisy (period 30 against a true 60 misses even a 200 spike), and its 3-cycle warm-up swallowed a real outage at period 288. Guessing a period is not safe
- [x] Mis-specification reported — spread ÷ volatility separates healthy series (0.73–0.96) from structured ones (1.93–10.08); `Detector.warmup()` now surfaces `unmodelled` beside `warm`, so a blind baseline is visible instead of quietly reporting `NORMAL`
- [ ] Period detection by autocorrelation, to make the opt-in automatic and safe *(Phase 5 — needs labelled scenarios to validate against)*
- [ ] ML detection — only if it beats the best statistical strategy on the benchmark *(Phase 5 decides)*

### 2.2 Correlation

- [x] N findings → 1 incident, gated by topology adjacency **and** time proximity — neither alone is sufficient
- [x] Unknown relationships default to **separate** incidents: splitting costs an operator a little confusion, merging gives them a fabricated causal chain and an inflated blast radius
- [x] Transitive grouping along a propagation chain, so a failure travelling three hops is one incident
- [x] Bounded adjacency depth — at enough hops everything reaches everything, and a test that always says yes is not a test
- [x] Incident inherits the full evidence trail, and takes its **strongest** finding's confidence rather than the average
- [x] Incorrect-merge measurement, reported **separately** from incorrect splits because they are not equally bad
- [x] Alert-to-incident compression ratio — read next to the merge rate, since compression is trivially maximized by merging everything
- [x] Verified on the demo scenario against the live graph: 5 findings → 2 incidents, zero incorrect merges
- [x] Must-not-merge case pinned in the labelled corpus (SC-0002) — two unrelated services degrading in the same minute stay two incidents, which time proximity alone would merge into one with a fabricated causal chain and an inflated blast radius
- [ ] Correlation window *tuned* by the benchmark rather than by judgement *(Phase 5 — 8 scenarios pin the behaviour but are far too few to tune a threshold against)*

### 2.3 AI Gateway

- [x] Vendor-neutral interface — the `Provider` protocol lives in `packages/core`, providers in `services/api`; **selected by configuration, never by an import**, so core never learns which one is in use — *evidence: CI gate fails if core imports a model SDK, or if anything outside `providers/` does*
- [x] Bedrock primary (Mantle client, Messages API — not the legacy InvokeModel path), direct API behind the identical shape; one request builder shared by both, so the two cannot drift
- [x] Structured outputs only — every call names a schema from a closed registry and receives a validated object. **No path returns free text**, because that path becomes the one everything uses and a parser is where an ungrounded claim gets laundered into a field the UI trusts
- [x] Schemas encode the grounding rule structurally: a claim sits beside a required `evidence_refs`, so an uncited hypothesis fails validation at the provider boundary rather than being suppressed later
- [x] Prompt-injection defense — instructions and evidence are separate fields that cannot be concatenated by accident; evidence is fenced, provenance-labelled, and fence-lookalikes are neutralised. *Evidence: a 6-case adversarial corpus asserting hostile content cannot escape its block* — **and cannot suppress its own ingestion**, since text that could delete itself would let an attacker blind the detector by writing a string into a log
- [x] Refusals and truncation are typed errors, not content — reading `content[0]` on a refusal raises something unrelated and sends the caller looking in the wrong place
- [x] Token accounting per incident, agent and purpose, checked **before** each call — a budget enforced after the spend is a report, not a limit
- [x] Bounded failure — retry with backoff, and a circuit breaker so a hung provider degrades one incident instead of silently stalling the loop meant to be diagnosing the outage. A schema violation deliberately does *not* trip it, or one bad schema takes a healthy provider offline
- [x] Evaluation harness — 4 regression cases run end to end on a deterministic stub provider, so schema, prompt assembly and accounting are exercised on every change without a credential or a cent. The stub **invents nothing**: a stub that fabricates findings makes a demo look like a working system
- [x] `/health` reports the provider, model and spend, with `configured: false` when the stub is answering *(evidence: 61 tests — 32 core, 29 api)*
- [ ] Cache-aware prompt assembly — stable prefix first, so multi-turn investigations stop paying full price *(deferred: needs real traffic to measure against)*

### 2.4 Reasoning

- [x] Hypothesis generation with confidence and mandatory evidence citations
- [x] **Citations are verified, not merely required** — the schema forces a ref to be *present*; admission checks it is *real*, against the events the incident holds. A model can satisfy every structural check by citing `evt-99`, and a fabricated citation is worse than a missing one: a missing one is visibly ungrounded, a fabricated one is indistinguishable from a good one until an operator clicks it
- [x] A partly-fabricated hypothesis is **dropped, not trimmed** — stripping the bad ref would leave the claim standing on evidence the model never had, which is the failure rather than the citation formatting
- [x] Suppression of unsupported hypotheses *(not low-confidence surfacing)* — a low-confidence hypothesis on screen is read as a lead, and someone spends an hour on it
- [x] **Suppression is counted and attributable**, never silent — a layer that discards most of what it produces is broken, and nobody finds out unless the discards show. Reported by reason, with a suppression rate
- [x] `contradicted_by` population — the system shows its own doubt. A *fabricated* counter-ref is dropped without killing the hypothesis, or a fabrication could suppress a well-supported finding
- [x] Change correlation — deployments matched against degradation onset, deterministically and without a model, since "did something change just before this broke?" is a question about timestamps. Deploys *after* onset are excluded; candidates are offered as citable evidence and **never as a conclusion**, holding the Phase 1 connector rule at the layer most tempted to break it
- [x] Causal chain assembly, each link citing its events — ordered by observation time rather than the model's narrative, because a model asked for a sequence produces one whether or not the timestamps agree. Built from admitted hypotheses only, so the chain cannot be where an unverified ref sneaks back in
- [x] No events means no speculation — the model is not called at all, since asking it to explain an incident with no telemetry is asking it to invent one
- [x] Measurement apparatus for the phase exit criterion — top-1 accuracy, precision-when-answering, and grounding reported **separately**, with abstentions counted against accuracy *(evidence: 28 tests)*
- [ ] Run it against 20 labelled incidents *(needs the Phase 5 scenario library — the apparatus exists, the corpus does not)*

### 2.5 Smriti — memory

- [x] Incident embedding and storage, with mandatory provenance — source, timestamp, owner, confidence, retention. Retention enforced **on read**, so an expired memory cannot resurface because a pruning job did not run
- [x] **Tenant isolation is structural, from the first commit** — `tenant` is a required positional argument on every read and no method reads across tenants. An unknown tenant returns empty rather than erroring, so the API cannot be used to enumerate which tenants exist
- [x] Hybrid retrieval — and the **match basis is reported, never blended into one score** ([ADR Smriti](adr/Smriti.md)). Two incidents both described as "connection pool exhausted" may share nothing but a phrase; no embedding model can separate them, because what distinguishes them is not in the prose. Matches are labelled `same_entity` / `same_signal` / `text_only`, ranked *within* a basis, and only the first two justify the phrase "we have seen this before"
- [x] The asymmetry that makes it hybrid rather than filtered — a text-only match must clear a similarity floor, a structural match need not. Filter-then-rank would lose the case where the same service failed before and nobody described it the same way, which is common and often the most useful recollection available
- [x] "We have seen this before" surfaced with the prior incident **and its outcome** — and the outcome is the valuable half. A wrong prior diagnosis, a failed remediation, or an unresolved incident is surfaced as a `CAUTION`, injected into the evidence the model sees rather than only the UI. Recalling a misdiagnosed incident silently lends the authority of history to a mistake, and the operator inherits it with more confidence than the person who made it
- [x] Nothing is recalled that was not stored — an unmatched query returns nothing and says so. A fabricated precedent is an uncited hypothesis one layer down, and harder to catch, because "we have seen this before" is exactly the claim people stop questioning
- [x] Runbook and architecture-decision ingestion — **always untrusted**, with no `trust=` parameter to pass `VERIFIED` to by accident. The only route to trusted is `promote()`, which requires a named actor and records them as owner
- [x] Wired into reasoning: precedents become citable evidence, so a recalled incident is a verifiable reference rather than a hint the model half-remembers. Past incidents are trusted (platform-authored); an unpromoted runbook is not *(evidence: 30 memory tests, 9 integration tests)*
- [x] Retrieval quality measurable — `false_precedents` reported **separately** from misses, since a missed precedent costs time the operator would have spent anyway while a false one sends them confidently down a path that does not exist
- [ ] Recall measured on real incident pairs, and a hosted embedder adopted on that evidence *(the local embedder is lexical: "pool exhausted" and "no free connections" will not match)*

### 2.6 Labelled corpus *(added — three deferred items all blocked on it)*

- [x] Scenario schema, strict loader, replay at a fixed epoch so results do not shift with the calendar
- [x] 8 scenarios in `benchmark/incidents/`, weighted toward cases this implementation could plausibly get wrong: a deploy that is a **red herring**, two unrelated failures in the same minute, a prior incident whose diagnosis was **wrong**, and a near-identical prior on an unrelated service
- [x] **Negative cases** (2) where the correct answer is silence — without them a system that flags everything scores perfectly — and an **escalation** case, without which the corpus rewards guessing over handing off
- [x] `scripts/benchphase2.py`, in CI, reporting **failures before passes**. Current: 0 false alarms, 0 missed, 0 mis-grouped, 0 false precedents, 8/8
- [x] The corpus found two real defects on its first run: it had **too few samples to warm a detector** (every incident missed — the detector was right to report `UNKNOWN`, the corpus was wrong), and the runner judged memory retention against wall-clock while dating it from a fixed epoch, so every precedent silently expired
- [x] SC-0003 confirms the [Seasonality](adr/Seasonality.md) work: robust-z does not fire on a genuine ramp, **and** the baseline reports `unmodelled: True` (structure 5.7) — it knows it is mis-specified there rather than being quietly confident

> **This is not PIB and must not be quoted as one.** It replays telemetry rather
> than injecting faults, and — unlike PIB — the scenarios were authored *after*
> the logic they score. One person wrote both the code and the answer key.
> Negative cases, adversarial cases and failure-first reporting reduce that; none
> of them eliminate it. It belongs in threats to validity, not a footnote.

**Exit criterion:** on 20 hand-labelled historical incidents, the top-1
root-cause hypothesis is correct ≥70% of the time, and every hypothesis cites
the telemetry supporting it.

**Status: NOT MET.** The corpus is 8 scenarios, not 20, and **reasoning quality
is not measured at all** — top-1 accuracy needs a real model, and scoring it
against the deterministic stub would measure a fixture this repository wrote. The
apparatus exists (`score_diagnoses`); the number is deliberately absent rather
than reported as a pass. Closing this needs a model credential and a larger
corpus. Detection, correlation and recall *are* genuinely scored and currently
pass.

**Risk:** the model produces a plausible but unsupported causal chain.
Mitigation — the evidence requirement is a validator, not a guideline.

---

## Phase 3 — Astra + Dharma · Action · Weeks 11–14 · Oct 19 – Nov 15

**Goal:** the system can act, and cannot act outside its bounds.

### 3.1 Already built (Phase 0)

- [x] Action registry with risk, expected post-state, rollback
- [x] Dharma policy engine and autonomy tiers
- [x] Guarded execution path — verdict required, bypass impossible
- [x] Append-only audit trail, written pre-execution
- [x] Dry-run default

### 3.2 Real executors

- [x] Kubernetes executor — restart, scale, rollback, redeploy, halt, via `kubectl` against the active kubeconfig. On EKS the same calls work unchanged; only authentication differs, and that is IRSA rather than anything in the file
- [x] Missing parameters refused rather than defaulted — `kubectl` with no namespace does not error, it targets `default`, which is a different part of the cluster than the caller meant
- [x] A timeout raises rather than assuming either outcome: a timed-out rollout may still be in progress, and guessing in either direction is worse than routing it to the rollback path
- [x] Ticketing and notification executors — escalation is a **registered action**, not application code. If telling a human is not an action it is not audited, not measured, and not something the policy layer can choose
- [x] **The guarded remediation loop** (`packages/core/pashupatastra/remediation.py`) — act → verify → roll back → escalate, with no cycles. The original action is **never retried**: it has already changed the system, and running it again changes it further while the diagnosis is in doubt
- [x] `ROLLBACK_FAILED` modelled as a first-class state, not an exception — the system acted, it did not work, the undo did not work, and the environment is in a state nobody designed. It pages a human **in prose**, because the reader has just been woken up and needs to know what state the system is in, not which enum was returned
- [x] An **unverified** rollback counts as a failed rollback — an undo that cannot be shown to have worked is indistinguishable from no undo, and assuming otherwise is how an environment drifts silently
- [x] An execution *error* also triggers rollback: the effect is ambiguous, and a rollback on an unchanged system is usually a no-op while skipping one on a changed system leaves it altered with nobody aware
- [x] Rollback tested for every action at runtime — *the registry guard proves an ID was written down; these walk the real registry, force each rollback, and assert it resolves and completes*. A second test asserts every rollback is **performable** by some executor, which the registry cannot see
- [x] Live execution opt-in — **two independent gates**, both required: `dry_run: false` *and* the environment named in `live_environments` (empty by default). One flag is one accident away from a production write. Every gate can veto; none can override, so a misconfiguration fails closed into dry-run *(evidence: 19 remediation tests, 23 executor tests)*
- [x] **Verified against a live kind cluster** — `scripts/verifyexecutors.py`, 11 checks, all passing against Kubernetes v1.36.1. Real rollout restart, real scale (cluster reports the new count), real `rollout undo` (revision advanced), a real missing-deployment error, and the full remediation loop rolling back for real
- [x] **The cluster run found two bugs the mocked tests could not**, which is why it was owed:
  - **The rollback ran with the original parameters.** Undoing a scale-to-5 by scaling to 5 would report success and change nothing — the most dangerous shape available here, since every layer above records a successful undo. Fixed with a `capture` step that snapshots prior state *before* acting; if the snapshot fails the loop refuses to act at all, because not acting costs an escalation while acting blind costs an unrecoverable change
  - **`restart_service` declares itself as its own rollback.** Repeating a restart undoes nothing, and Kubernetes rejects two restarts within a second — which surfaced as `ROLLBACK_FAILED`, a page for a state that was never broken. The registry's guard is satisfied by *declaring* an ID; it cannot tell that repeating an action undoes it. A self-rollback with no captured prior state now escalates instead
- [ ] **Registry gap, pinned not patched:** `restart_service` and `modify_db_config` declare themselves as their rollback while undoing nothing (`scale_service` is the legitimate case — genuinely its own inverse, but only with different parameters). Deciding what the rollback of a restart *should* be is a policy question, and the current binary rollback-or-irreversible model cannot express "low risk, self-healing, not undoable"
- [ ] Cache executor — flush, warm *(registered and deniable by policy, but no executor performs them; an unowned action fails loudly rather than appearing to succeed)*

### 3.3 Agent runtime

- [x] Loads declarations and enforces tool allow-lists **at call time, not load time** — a runtime that validates once and then trusts itself is one refactor away from a tool acquired mid-run being callable. *Evidence: a test mutates the declaration after construction and the next call is still refused*
- [x] An undeclared callable is never even held, so a bug cannot reach one — belt and braces on top of the call-time check
- [x] Denied calls are **recorded, not discarded**: an agent repeatedly reaching for something it cannot have means its declaration is too narrow or its prompt is wrong, and dropping those attempts hides it
- [x] Budget enforcement — tokens, actions, wall clock, all checked **before** the spend. Enforced afterwards, a budget is a report of where it stopped rather than a ceiling
- [x] Exhaustion **escalates** rather than failing silently or continuing — a runaway loop that quietly stops looks identical to a task that finished, and the incident sits untouched while everyone believes an agent has it
- [x] A refused action does not spend the action budget: charging for a refusal would make the budget punish caution
- [x] **The risk ceiling is enforced above approval** — an agent with limit 40 cannot execute a risk-45 action *even with a human granting it*. Approval answers "may this be done"; the ceiling answers "may this actor do it", and collapsing them lets an agent escalate its own authority by asking nicely
- [x] Escalation paths with reasons recorded; the **first** reason wins, since it is the true one and everything after is a consequence
- [x] MVP fleet — `sati.orchestrator`, `sati.incident`, `sati.infrastructure`, `sati.security`. The orchestrator has **risk limit 0** (one that can act accumulates the union of every role's authority without declaring it) and security is **read-only by declaration** (the role an attacker most wants to reach). Tested to have genuinely different tool sets, since four identical specs would satisfy least-privilege in form and none of its intent
- [x] Every role is dev-only, pinned by a test — if it starts failing, someone widened production authority, and that should be a visible diff
- [x] **Verified live**: `sati.infrastructure` scaled a real deployment through the runtime, was refused an undeclared tool, and had a risk-65 action denied by Dharma against its ceiling of 45 *(16 live checks, 25 runtime tests)*

### 3.4 Approval UX

- [x] Plan presentation — the approval surface already renders the risk arithmetic, blast radius, expected post-state and rollback *(built in Phase 1)*
- [x] One-click approve with the approver recorded, plus `POST /policy/deny`
- [x] **Denial is a first-class outcome, not an HTTP error** — expressing it as an error would make the client's success path the one where a human said yes, which is exactly the wrong pressure to build into a UI
- [x] **A stale verdict fails loudly (409) rather than quietly succeeding.** `is_executable` already refused expired verdicts, but only later and somewhere else — leaving the operator believing they had authorised something. Expiry is now visible at the moment of clicking
- [x] Expiry counted **apart from denials**: an unanswered request means the routing or the load is wrong, which is a different problem from a considered no
- [x] **Approval fatigue guard** (`packages/core/pashupatastra/approvals.py`) — a policy layer that routes risky actions to a human is only a safety mechanism if the human is deciding. Approving everything in two seconds makes the tier system a speed bump with an audit trail, and is arguably **worse than no approval step**, because it manufactures accountability: an operator's name sits on a decision they did not make, and everyone downstream reads it as evidence the action was considered
- [x] **The signal is a combination, and is deliberately not collapsed into one score.** A high approval rate alone is what a well-calibrated system produces; a fast decision alone may be entirely informed. Only *near-total approval together with near-instant decisions* indicates a formality — and both halves are tested to be innocent on their own
- [x] "Too fast to have read" is named for what it measures — elapsed time — not for what it implies. The system cannot see attention, and presenting an inference as an observation is the error the reasoning layer exists to avoid
- [x] Timed from **presentation, not verdict issuance**: the gap between Dharma deciding and an operator seeing the request is queueing, and charging it to the human would flatter every number
- [x] Below 10 decisions the verdict is `None`, not a reassuring `False` — "not enough evidence" and "no problem" are different claims, and only one should let someone stop worrying
- [x] Per-approver breakdown, because one person waving everything through behind a healthy team average is a different problem from a uniformly rushed team
- [x] Exposed at `GET /policy/approvals/fatigue`, summary leading with the uncomfortable number — a metric nobody looks at cannot change behaviour *(evidence: 18 core tests, 8 API tests)*
- [ ] Wire the web approve button to the endpoint *(the surface renders; the click is not yet bound)*
- [ ] Persist approvals alongside the audit trail — fatigue numbers are per-process until then, so a restart currently resets the measurement

### 3.5 AWS enforcement floor

The point of this section is that the runtime's guarantees survive a mistake *in
the runtime*. `AgentRuntime` refuses an undeclared tool and Dharma refuses an
action above a ceiling — both are Python, and Python can be wrong. IAM is the
floor beneath them.

- [x] IRSA role per agent, mirroring its declared permissions — one role, one service account, with a `sub` condition so no other pod can assume it (without that, per-agent roles are decorative)
- [x] **The mirror is checked, not hoped for.** `infra/terraform/agents.json` is a single source of truth shared by Terraform and the test suite; 14 tests assert its tool lists match `sati_roles()` exactly. Drift is the real failure mode here — when the declaration and the credential disagree, the weaker one is the actual policy, and a reader looking at either alone draws the wrong conclusion
- [x] Read and write roles separated, as distinct policies rather than one merged document — so an agent with no write access has **no write policy attached at all**, visible in `terraform plan` rather than an empty statement nobody reads
- [x] Risk-limit-0 agents are asserted to hold zero write permissions, so `sati.orchestrator` and `sati.security` cannot be granted write access without failing CI
- [x] **Destructive permissions granted to no role, in any environment** — an explicit `Deny` attached to every agent role. A deny-list is usually the weaker pattern; here it is the only one that **cannot be out-voted by a well-meaning Allow added under time pressure**, because explicit Deny always wins in IAM. Covers cluster/database/bucket deletion, `iam:*` (without which an agent could grant itself everything else on the list), and `cloudtrail:StopLogging` — an agent that can silence CloudTrail can act without a second record
- [x] The credential is strictly weaker than the action registry: the registry governs what the platform will *choose* to do, IAM what its credentials *can* do
- [x] `terraform fmt`, `validate`, and **`plan` against the real AWS provider** — 11 to add, 0 to change, 0 to destroy; `agents_without_write_access` correctly reports `sati.orchestrator` and `sati.security`
- [x] Secrets Manager for the database credential, generated by Terraform and never in state output *(built in Phase 0.9)*
- [ ] **Apply it.** The plan is verified; nothing has been provisioned. Needs a deliberate decision, since RDS costs money
- [ ] Agent roles are skipped until an EKS OIDC provider exists — a cluster-less environment plans clean by design, so this lands with the cluster
- [ ] KMS customer-managed keys for connector credentials *(Secrets Manager uses the AWS-managed key today)*

**Exit criterion:** a red-team pass finds no execution path that reaches a
connector without a recorded policy verdict; every action has a tested rollback;
CloudTrail confirms no action occurred that the internal audit log does not
record.

**Risk:** this is where the project can do real damage. Mitigation — dry-run
default, per-environment opt-in, blast-radius escalation regardless of score.

---

## Phase 4 — Verification · Weeks 15–17 · Nov 16 – Dec 6

**Goal:** the loop closes. The system knows whether it actually fixed anything.

### 4.1 Already built (Phase 0)

- [x] Expected-state contracts declared before execution
- [x] Threshold grading — `<70%`, `>99%`, equality
- [x] Missing observation grades as failure, never as success
- [x] Verification results audited

### 4.2 Live verification

- [x] Post-action observation window against real telemetry — verified against a live kind cluster by `scripts/verifywindow.py`: a healthy deployment holds across consecutive samples, an unpullable image reports `never_reached` rather than recovered, and recovery after a rollback is observed as held
- [x] Per-action window tuning — a restart settles faster than a rollback
- [x] Automatic rollback on verification failure — graded over the window, so a metric that merely bounces no longer closes the incident
- [x] Escalation when rollback itself fails *(the worst case, and it must be handled)*
- [x] Settling is named rather than boolean — `held`, `never_reached`, `flapping`, `regressed`, `timed_out`. "Never recovered" and "recovered then lost it" lead somewhere different, and a boolean cannot carry that

### 4.3 Learning

- [x] Outcomes written back to Smriti — successes and failures with equal prominence. Enforced structurally: one `learn()` path with no success-only branch, and a test asserting a failure is stored with the same kind, retention and trust as a success. Equal prominence stated in a docstring is not equal prominence
- [x] Novelty penalty fed by execution history — familiarity is per environment, because succeeding in dev says nothing about prod, and expires at a horizon since an action last run against infrastructure that has since been rebuilt is closer to novel than familiar
- [x] Tried-and-failed distinguished from never-tried, and it raises risk. Repeated failure pushes an action out of `AUTONOMOUS`, so the loop stops quietly retrying something that keeps not working
- [x] Estimation error tracked — predicted vs. actual blast radius, signed rather than absolute. Under-estimating is the direction that lets an action run autonomously when it should have gone to a human, and a mean absolute error reports it identically to the harmless direction
- [x] The loop is wired into a live execution path — `POST /actions/remediate` runs act → observe over a window → roll back → learn, behind the same dry-run gates as every other write
- [x] A rollback is authorised by its own Dharma verdict. `require_verdict` binds a verdict to one action ID, so the one issued for the original action cannot authorise its undo — reusing it would be a policy bypass wearing the shape of a convenience
- [x] A mismatched verdict is refused **before** the loop starts. `Remediator` treats any runner exception as "the execution failed" and responds by rolling back, so a `PolicyViolation` swallowed there would turn an unauthorised request into a real rollback undoing something that never ran
- [x] Prior state captured before acting — replicas before a scale, image before a redeploy — so an undo restores rather than repeats
- [x] Dry-run returns unobserved immediately instead of opening a window. Nothing changed, so there is nothing to wait for, and unobserved still never counts as success

### 4.4 Timeline UI

- [x] Detection → hypothesis → plan → approval → execution → verification, drawn as six fixed stages rather than assembled from audit records. A timeline built from records shows what happened and silently omits what did not, so an incident that closed without verifying would render identically to one that verified cleanly — the reader would have to notice an absence
- [x] A stage the loop passed over is labelled `never ran` and says so in words, distinct from `not yet`
- [x] `resolved` is deliberately **not** accepted as evidence that verification ran. Reaching resolved is the claim that the fix worked, and verification is what justifies that claim; accepting it would hide the exact anomaly the timeline exists to surface — *evidence: a probe incident resolved without verifying renders `never ran`, while the normal incident renders no false alarm*
- [x] Every step linked to its audit record and evidence — each stage links to the specific audit rows it claims, by anchor, rather than to the trail in general
- [ ] Frontend has no test framework, so the timeline is verified by rendering rather than by test. Worth adding before the logic grows

**Exit criterion:** verification correctly classifies success and failure on 20
injected faults, including deliberately wrong remediations.

---

## Phase 5 — PIB · Benchmark · Weeks 18–20 · Dec 7 – Dec 27

**Goal:** claims become numbers.

### 5.1 Scenario library

- [x] Scenario schema and validator — `packages/core/pashupatastra/pib.py`, separate from the Phase 2 replay corpus so benchmark results and development measurements cannot be confused for each other
- [x] The validator rejects rather than warns. Each rule blocks a mistake that is invisible in one file and silently changes what the benchmark measures: an expected action missing from its own allow-list, an action both allowed and forbidden, a remediate case with no recovery state and therefore no answer to "did it work?"
- [x] 100+ scenarios across the eight seed categories — 104, validated by `python scripts/validatepib.py`
- [x] **Negative scenarios** — 25, and present in *every* category. Aggregate counts hide the real failure: all the negatives in one category is negatives on paper and blind spots in the other seven
- [x] **Escalation scenarios** — 19, likewise per category, each stating why it escalates so the grader can tell a correct hand-off from a system that gave up
- [x] A negative case cannot carry an expected action and an escalation case cannot expect a remediation — enforced by the validator, since either would score a system that acted as correct and reward exactly the behaviour the category exists to penalise
- [x] `security` is deliberately escalation-heavy — 5 escalations to 4 remediations. Revoking a credential, judging an exfiltration, or confirming a supply-chain compromise are human calls, and shaping that category like the others would teach the wrong lesson
- [x] All scenarios authored **before** the logic that resolves them — the harness (5.2) does not exist yet

### 5.2 Harness

- [x] Fault injection against the real containerized stack — `benchmark/harness/`, real `kubectl` changes producing real unavailable replicas and real rollout history, not simulated telemetry
- [x] Ephemeral environment — a namespace per run, torn down in `__exit__` so it happens on success, failure and interrupt alike. A run inheriting the previous run's broken deployment produces a result about the wrong fault and nothing in the output would say so
- [x] N runs per scenario; variance reported **per scenario**, not as a mean. Passing 3 of 5 and passing 5 of 5 average to "mostly fine" and only one is a system you would turn on, so mixed results are flagged `UNSTABLE` by name
- [x] One-command reproducibility — `python -m benchmark.harness.run --runs 3 --arm none`
- [x] Harness errors are graded separately and excluded from the failure rate — a rig that could not set up the fault has said nothing about the system, and folding it in makes a flaky cluster look like a wrong answer
- [x] **Only 31 of 104 scenarios (30%) are runnable, and the other 73 are excluded by name with a stated reason.** An exclusion with no reason raises. The alternative is a harness that runs what is easy and reports it as the corpus, and the easy scenarios are biased in exactly the direction that flatters the system
- [x] The runnable subset is **not representative**, and the runner says so on every invocation: 20 negatives, 6 escalations, 5 remediations. A score from it flatters restraint and is not a corpus score
- [ ] The excluded 70% — needs a load generator, an instrumented reference application, and a stateful database. Until then the benchmark cannot grade `error_rate`, `latency_p95_ms`, or any application metric, which is most of the corpus

### 5.3 Arms

- [x] **Arms never receive the scenario.** They get a `Brief` — live stack state, permitted actions, risk ceiling — because the scenario carries `expected.action` and an arm holding the answer key would score perfectly while measuring nothing. This was a real flaw in the 5.2 harness; redaction is now structural and `testarms.py` fails if a field carrying the answer is added back
- [x] **Traditional runbook automation** — fires on a threshold, no policy evaluation, no verification, structurally cannot escalate
- [x] **Pashupatastra, full architecture** — same proposal as the runbook arm, then Dharma decides and the result is verified. Holding the proposal constant is what isolates the architecture as the variable
- [~] **Naive LLM agent** — implemented as a code path that **refuses to run without a configured model**. Driving it with the deterministic stub would produce a second runbook wearing a different label, and reporting that as an LLM baseline would be the one purely fabricated result in the benchmark
- [ ] **Human operator with standard dashboards** — not implementable. Blocked on recruiting operators; protocol and recording format are in `benchmark/results/human/`. A simulated human is this repository writing the number it wants the baseline to produce, in the one place nobody would check
- [x] Diagnosis quality is deliberately **not** what separates the arms. It needs a real model, and scoring the stub would measure a fixture this repo wrote — so the shared proposer is identical across arms and only the architecture around it differs

### 5.4 Ablations

- [x] **Without policy tiers** — `--ablation no-policy`. The gate is removed and nothing else, so the arm acts where it should hand off
- [x] **Without the verification stage** — `--ablation no-verification`. Reports the action as done without checking, which is what a system with no verification genuinely does
- [ ] Without the hypothesis evidence requirement — **refuses to run.** It lives in the reasoning layer, which the benchmark arm never invokes; the shared proposer stands in for diagnosis because there is no model
- [ ] Without Smriti retrieval — **refuses to run.** Not part of this arm's decision path; each scenario runs in a fresh namespace with no prior incidents to recall
- [ ] Without topology-adjacency correlation — **refuses to run.** Correlation happens before an incident is formed, and the harness hands the arm one already-scoped fault
- [x] An ablation the arm cannot exercise raises rather than running. Removing a stage that never ran produces an identical score and would be reported as *"no effect"* — the most misleading result available here, because it reads as evidence the component does not matter

### 5.5 Reporting

- [x] Metrics computed from the run record alone — every run appends to `benchmark/results/**/runs.jsonl`, and `scripts/pibreport.py` reads that and nothing else. It never imports the harness, which is the point: a number nobody else can reproduce is a claim rather than a measurement
- [x] False remediation rate reported **before** autonomous resolution rate, in the table and in the summary dict. ARR is trivially maximised by acting recklessly, and whichever number is read first is the one that gets quoted
- [x] FRR and VSR are rates over **actions actually executed**. Deriving "acted" from the verdict counted every correct negative — where the right answer was to do nothing — as an executed action, inflating the denominator with runs that touched nothing and making the safety metric look far better than it was
- [x] Per-scenario results published, not only aggregates, with mixed runs flagged `UNSTABLE`
- [x] Any excluded scenario states its reason in the table; an exclusion with no reason raises
- [x] Human-intervention rate broken down by **where autonomy stopped** — policy ceiling, verification failure, unrecognised situation — carried as a token rather than parsed back out of prose
- [x] Three of METRICS.md's eight metrics are **not computable** here and are printed as absent with reasons — RCA needs the reasoning layer, detection accuracy is never exercised, and the recorded clock is not MTTR's clock. A table showing five of eight with no note reads as complete
- [ ] Runs against both the AWS stack and the compose stack — only the kind cluster so far

#### The ordering confound, found and fixed

The first full comparison gave Pashupatastra 31/31. It was largely an artefact:
the corpus listed each scenario's expected action **first** in `allowed_actions`
(44 of 60 scenarios, 5 of 5 runnable), and the shared proposer picks
`allowed_actions[0]`. Every remediation both arms got right was won by list
order rather than by diagnosis. `allowed_actions` is now sorted, so position
carries no signal, and the corpus was regenerated and re-run.

**Exit criterion:** the full benchmark runs reproducibly from one command and
produces the metrics table.

**Risk:** benchmarking against yourself proves nothing. Mitigation — scenarios
authored first, negative cases included, failure reported first.

---

## Phase 6 — Research & Open-Source Release · Weeks 21–24 · Dec 28 – Jan 24 2027

### 6.1 Paper

- [ ] Draft — *Pashupatastra: Policy-Constrained Closed-Loop Autonomous Infrastructure Operations*
- [ ] Results and ablation tables
- [ ] Threats to validity stated plainly, including the self-authored benchmark
- [ ] Failure analysis — what the escalation cases have in common
- [ ] Submission or arXiv preprint

### 6.2 Open source

- [ ] Split the monorepo — core, agent, sdk, connectors, benchmark, docs, ui, examples
- [ ] License, contribution guide, vulnerability disclosure process
- [ ] Reproducibility: benchmark runnable by a third party on release day

### 6.3 Commercial

- [ ] Pashupatastra Cloud — enterprise dashboard, multi-cluster, SSO, compliance, SLA
- [ ] On-prem distribution built from the compose stack

### 6.4 Launch

- [ ] Website — product-grade, animated architecture, research link
- [ ] Demo video — the killer demo, unedited, end to end

---

## The killer demo

The single artifact that tells the whole story. Build toward it from Phase 1.

1. Healthy reference stack on screen.
2. Inject database connection exhaustion via a bad deployment (v4.21).
3. Pashupatastra raises **one** incident, not five alerts — severity, affected
   service, estimated users affected, root-cause probability.
4. Causal chain renders: `deploy v4.21 → query increase → connection saturation
   → request queue → timeout → 5xx → failed transactions`.
5. Remediation plan with risk score, blast radius, and rollback.
6. Operator clicks **Approve**.
7. Verification checklist turns green line by line.
8. **Incident resolved.**

Status: steps 3–6 render today from seeded data. Steps 1, 2, 7, and 8 need live
connectors and real executors.

---

## Beyond V1

| Version | Scope |
|---------|-------|
| V1 | Infrastructure intelligence |
| V2 | Autonomous DevOps |
| V3 | AI cyber defense — **[KAVACH.md](KAVACH.md)**, Phases 7–12 |
| V4 | Enterprise systems intelligence |
| V5 | Physical + digital systems — factories, machines, robots, IoT |

The cyber defense program is planned in full in [KAVACH.md](KAVACH.md). It
extends this roadmap rather than replacing it: Phases 0–6 close the loop over
infrastructure, Phases 7–12 close the same loop over adversaries, reusing the
event model, graph, detection harness, policy engine and audit trail unchanged.
Two hard gates connect them — the Phase 2 seasonality gap blocks Phase 9, and the
Phase 3 executors block Phase 10.

Task-level breakdowns for every phase live in [TASKS.md](TASKS.md).

**Kaal** (digital twin / simulation) slots in after Phase 4: answer "what happens
if I restart PostgreSQL?" *before* acting — expected downtime, affected services,
users impacted, recovery probability. This is the step from monitoring to
decision intelligence.

## Business model

| Tier | Price | Scope |
|------|-------|-------|
| Developer | Free | 1 environment, limited agents, OSS core, community support |
| Team | $99–299/mo | Multiple environments, AI incident analysis, automation, teams |
| Business | $1,000+/mo | Advanced agents, security, policy controls, audit, SSO |
| Enterprise | Custom | On-prem, private deployment, compliance, SLA, dedicated support |

On-prem and hybrid deployment is the deliberate wedge — underserved relative to
cloud-native, and where the policy and audit story sells hardest.

## Founding thesis

> Software systems have become too complex for humans to operate through
> dashboards and alerts alone. Pashupatastra is building an intelligence layer
> that understands system state, reasons about cause and consequence, and safely
> executes verified actions under explicit human-defined policies.
