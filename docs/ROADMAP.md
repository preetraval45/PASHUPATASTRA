# Plan of Action

**Pashupatastra — 24-week path from empty repository to research release.**

Each phase has a hard exit criterion. A phase is not done when the code is
written; it is done when the criterion is demonstrably met. Phases 1–4 build the
loop in the order the loop runs, so every phase ends with something
demonstrable rather than a half-wired layer.

---

## Phase 0 — Foundation · Weeks 1–2

**Goal:** every constraint that governs the system is written down before code
can violate it.

| # | Deliverable | Exit criterion |
|---|-------------|----------------|
| 0.1 | Repository scaffold, README, CLAUDE.md | ✅ done (memory 0001) |
| 0.2 | `docs/ARCHITECTURE.md` — subsystems, data flow, boundaries | ✅ done |
| 0.3 | ADR 0001 monorepo boundaries, ADR 0002 event schema | Both merged |
| 0.4 | Normalized event model in `packages/core/` | Pydantic schemas + round-trip tests |
| 0.5 | Database schema (Postgres) — incidents, actions, audit, topology | Migrations run clean |
| 0.6 | OpenAPI specification for the gateway | Spec lints; mock server serves it |
| 0.7 | Agent specification — identity, tools, budget, risk limits | YAML schema + validator |
| 0.8 | Security & threat model | Documented, reviewed |
| 0.9 | Design system tokens + logo direction | Tokens in `apps/web` |
| 0.10 | **Name clearance** — USPTO, state corporate name, `.com/.ai/.dev`, GitHub org, LinkedIn, social handles | Written go/no-go decision |

**Blocker:** 0.10 gates all public activity. Build under the name; do not launch,
incorporate, or buy a domain portfolio under it until this clears.

**Risk:** over-specifying schemas before real telemetry exists. Mitigation —
version the event schema from v0 and treat Phase 1 as the first migration test.

---

## Phase 1 — Drishti · Perception · Weeks 3–6

**Goal:** heterogeneous telemetry becomes one normalized stream and one live
topology.

- Connectors: Prometheus, OpenTelemetry, Elasticsearch, Docker, Kubernetes
- Normalization into the core event model; provenance stamped on every event
- Topology/knowledge graph construction — services, dependencies, ownership
- Blast-radius traversal: given a node, who is downstream and how many users
- Infrastructure map + service map in the dashboard

**Exit criterion:** point Pashupatastra at a live 5-service reference stack; the
graph auto-builds within 60s and blast radius for any node is queryable in
under 200ms.

**Risk:** connector sprawl eats the phase. Mitigation — Prometheus + Kubernetes
only until the graph is correct; the rest are additive afterward.

---

## Phase 2 — Buddhi + Smriti · Intelligence · Weeks 7–10

**Goal:** signals become one incident with a defensible causal chain.

- Anomaly detection (statistical baseline first, ML second)
- Correlation: N alerts → 1 incident, scoped by topology adjacency and time
- Causal hypothesis generation with confidence scores and provenance
- **Smriti**: incident embedding + retrieval — "we have seen this before"
- Deployment/change correlation — the single highest-yield causal signal
- AI Gateway: vendor-neutral, structured outputs, evaluation harness

**Exit criterion:** on 20 hand-labelled historical incidents, top-1 root-cause
hypothesis is correct ≥70% of the time and every hypothesis cites the telemetry
that supports it.

**Risk:** the model hallucinates a plausible causal chain. Mitigation — a
hypothesis that cannot cite retrieved evidence is suppressed, not surfaced with
low confidence.

---

## Phase 3 — Astra + Dharma · Action · Weeks 11–14

**Goal:** the system can act, and cannot act outside its bounds.

- Action registry: restart, scale, rollback, clear cache, disable deployment,
  create ticket, notify — each declaring risk score, expected post-state, rollback
- **Dharma** policy engine: risk tiers → autonomous / approval / senior / never
- Agent runtime: identity, permissions, tools, memory, budget, risk ceiling
- MVP agent set: Incident, Infrastructure, Security + one orchestrator
- Approval UX: plan, blast radius, expected outcome, one-click approve
- Append-only audit trail for every decision and execution

**Exit criterion:** a red-team pass finds no execution path that reaches a
connector without a recorded policy verdict; every action has a tested rollback.

**Risk:** this is where the project can do real damage. Mitigation — dry-run
mode is the default; live execution is opt-in per environment; blast radius
above a configured threshold always escalates regardless of risk score.

---

## Phase 4 — Verification · Weeks 15–17

**Goal:** the loop closes. The system knows whether it actually fixed anything.

- Expected-state contracts declared before execution
- Post-action observation window and comparison
- Automatic rollback on verification failure
- Outcome written back to Smriti — this is the learning signal
- Incident timeline UI: detection → hypothesis → plan → approval → execution → verification

**Exit criterion:** verification correctly classifies success/failure on 20
injected faults including deliberately wrong remediations.

---

## Phase 5 — PIB · Benchmark · Weeks 18–20

**Goal:** claims become numbers.

Build **PIB — Pashupatastra Incident Benchmark**: 100–500 controlled incidents.
Each specifies input telemetry, expected diagnosis, expected action, allowed
actions, risk level, expected recovery state.

Seed scenarios: DB connection exhaustion · Redis memory leak · CPU saturation ·
disk exhaustion · bad deployment · broken API dependency · certificate
expiration · DNS failure · crash loop · unauthorized login · credential exposure ·
network latency · memory leak · queue backlog.

Baselines: human operator · traditional runbook automation · naive LLM agent ·
Pashupatastra.

Metrics: MTTR · autonomous resolution rate · **false remediation rate** ·
verification success rate · blast radius · human intervention rate · root-cause
accuracy.

**Exit criterion:** full benchmark runs reproducibly from one command and
produces a metrics table.

**Risk:** benchmarking against yourself proves nothing. Mitigation — scenarios
are authored before the fix logic, and false remediation rate is reported as
prominently as success rate.

---

## Phase 6 — Research & Open-Source Release · Weeks 21–24

- **Paper:** *Pashupatastra: Policy-Constrained Closed-Loop Autonomous
  Infrastructure Operations*
- **Open source** `pashupatastra-core`: event schema, agent framework, policy
  engine, connectors, incident model, benchmark, SDK. Split the monorepo here.
- **Commercial** `Pashupatastra Cloud`: enterprise dashboard, advanced agents,
  multi-cluster, security, compliance, teams, audit, SLA.
- **Website:** product-grade landing page, animated architecture, research link.
- **Demo video:** the killer demo below, unedited and end-to-end.

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
if I restart PostgreSQL?" *before* acting — expected downtime, affected
services, users impacted, recovery probability. This is the step from monitoring
to decision intelligence.

## Business model

| Tier | Price | Scope |
|------|-------|-------|
| Developer | Free | 1 environment, limited agents, OSS core, community support |
| Team | $99–299/mo | Multiple environments, AI incident analysis, automation, teams |
| Business | $1,000+/mo | Advanced agents, security, policy controls, audit, SSO |
| Enterprise | Custom | On-prem, private deployment, compliance, SLA, dedicated support |

On-prem and hybrid deployment is the deliberate wedge — it is underserved
relative to cloud-native, and it is where the policy/audit story sells hardest.

## Founding thesis

> Software systems have become too complex for humans to operate through
> dashboards and alerts alone. Pashupatastra is building an intelligence layer
> that understands system state, reasons about cause and consequence, and safely
> executes verified actions under explicit human-defined policies.
