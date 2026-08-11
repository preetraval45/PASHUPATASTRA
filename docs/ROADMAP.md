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
- [x] AWS credential handling — no long-lived keys, SSO/IRSA/OIDC
- [x] `.gitignore` covers `.env`, keys, `*.tfstate`
- [x] Secret scanning in CI — gitleaks
- [ ] Threat model reviewed by a second person — **blocked: needs a human reviewer**

### 0.8 Frontend foundation

- [x] Next.js app, TypeScript strict, Tailwind
- [x] Design tokens — restrained palette, no mythological ornament
- [x] Logo — mark, horizontal lockup with tagline, and `docs/BRAND.md`
- [x] Geometric mark — loop, shaft, decision node, trident head; teal is perception, gold is action
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
- [ ] Written go/no-go decision recorded as an ADR

**This gates all public activity.** Build under the name; do not launch,
incorporate, or buy a domain portfolio until it clears. A domain being available
is not evidence the trademark is.

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
- [ ] **Seasonality gap — measured, not suspected.** The shipped robust-z default scores 859 false alarms per 1000 on a daily-shaped series; EWMA scores 43. A detector that cries wolf every morning is one operators learn to ignore
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
- [ ] Correlation window tuned by the benchmark rather than by judgement *(Phase 5)*

### 2.3 AI Gateway

- [ ] Vendor-neutral interface — Bedrock primary, direct APIs behind the same shape
- [ ] Structured outputs only; validated schemas, no free-text parsing
- [ ] Prompt-injection defense — telemetry quoted as data, never as instruction
- [ ] Token accounting per incident, feeding agent budgets
- [ ] Evaluation harness with regression cases

### 2.4 Reasoning

- [ ] Hypothesis generation with confidence and mandatory evidence citations
- [ ] Suppression of unsupported hypotheses *(not low-confidence surfacing)*
- [ ] `contradicted_by` population — the system shows its own doubt
- [ ] Change correlation — deployments matched against degradation onset
- [ ] Causal chain assembly, each link citing its events

### 2.5 Smriti — memory

- [ ] Incident embedding and storage
- [ ] Hybrid retrieval — embeddings plus structured entity/symptom filters
- [ ] "We have seen this before" surfaced with the prior incident and its outcome
- [ ] Runbook and architecture-decision ingestion

**Exit criterion:** on 20 hand-labelled historical incidents, the top-1
root-cause hypothesis is correct ≥70% of the time, and every hypothesis cites
the telemetry supporting it.

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

- [ ] Kubernetes executor — restart, scale, rollback, halt deployment
- [ ] Cache executor — flush, warm
- [ ] Ticketing and notification executors
- [ ] Rollback tested for every action — *the registry guard is compile-time; this is runtime*
- [ ] Live execution opt-in, per environment, off by default

### 3.3 Agent runtime

- [ ] Loads declarations, enforces tool allow-lists at call time
- [ ] Budget enforcement — tokens, actions, wall clock; exhaustion escalates
- [ ] Escalation paths with reasons recorded
- [ ] MVP fleet — orchestrator plus Incident, Infrastructure, Security agents

### 3.4 Approval UX

- [ ] Plan presentation — steps, risk breakdown, blast radius, expected outcome
- [ ] One-click approve with the approver recorded
- [ ] Denial and escalation surfaced as first-class outcomes, not errors
- [ ] Approval fatigue guard — measure how often approvals are rubber-stamped

### 3.5 AWS enforcement floor

- [ ] IRSA role per agent, mirroring its declared permissions
- [ ] Read and write roles separated
- [ ] Destructive permissions granted to no role, in any environment
- [ ] Secrets Manager + KMS for all connector credentials

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

- [ ] Post-action observation window against real telemetry
- [ ] Per-action window tuning — a restart settles faster than a rollback
- [ ] Automatic rollback on verification failure
- [ ] Escalation when rollback itself fails *(the worst case, and it must be handled)*

### 4.3 Learning

- [ ] Outcomes written back to Smriti — successes and failures with equal prominence
- [ ] Novelty penalty fed by execution history
- [ ] Estimation error tracked — predicted vs. actual blast radius

### 4.4 Timeline UI

- [ ] Detection → hypothesis → plan → approval → execution → verification
- [ ] Every step linked to its audit record and evidence

**Exit criterion:** verification correctly classifies success and failure on 20
injected faults, including deliberately wrong remediations.

---

## Phase 5 — PIB · Benchmark · Weeks 18–20 · Dec 7 – Dec 27

**Goal:** claims become numbers.

### 5.1 Scenario library

- [ ] Scenario schema and validator
- [ ] 100+ scenarios across the eight seed categories
- [ ] **Negative scenarios** — degradations where the correct answer is to do nothing
- [ ] **Escalation scenarios** — where the correct answer is to hand off
- [ ] All scenarios authored **before** the logic that resolves them

### 5.2 Harness

- [ ] Fault injection against the real containerized stack
- [ ] Ephemeral environment — provisioned per run, torn down after
- [ ] N runs per scenario; variance reported
- [ ] One-command reproducibility

### 5.3 Arms

- [ ] Human operator with standard dashboards
- [ ] Traditional runbook automation
- [ ] Naive LLM agent — tools, no policy layer, no verification
- [ ] Pashupatastra, full architecture

### 5.4 Ablations

- [ ] Without the hypothesis evidence requirement
- [ ] Without Smriti retrieval
- [ ] Without topology-adjacency correlation
- [ ] Without the verification stage
- [ ] Without policy tiers

### 5.5 Reporting

- [ ] Metrics computed from the audit log alone, by the definitions in `research/METRICS.md`
- [ ] False remediation rate reported **before** autonomous resolution rate
- [ ] Per-scenario results published, not only aggregates
- [ ] Any excluded scenario states its reason in the table
- [ ] Runs against both the AWS stack and the compose stack

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
| V3 | AI cyber defense (**Kavach** expands) |
| V4 | Enterprise systems intelligence |
| V5 | Physical + digital systems — factories, machines, robots, IoT |

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
