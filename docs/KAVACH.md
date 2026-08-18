# Kavach — Cyber Defense Program

**Pashupatastra Kavach — a 36-week path from a working operations platform to a
research-grade autonomous cyber defense system.**

This document continues [ROADMAP.md](ROADMAP.md). It does not replace it. Phases
0–6 build the closed loop over *infrastructure*; Phases 7–12 build the same loop
over *adversaries*. The numbering is continuous because the substrate is shared,
not merely similar.

Maintained under the same protocol as ROADMAP.md: a task is ticked only when its
evidence exists — a passing test, an applied migration, a committed decision. See
[CONTRIBUTING.md](CONTRIBUTING.md).

| Mark | Meaning |
|------|---------|
| `- [x]` | Done, and its evidence exists |
| `- [~]` | Partly done. The line says exactly what remains |
| `- [ ]` | Not started |

---

## Why this is an extension and not a pivot

A cyber defense platform and an autonomous operations platform differ in their
data and their adversary. They do not differ in their spine. Kavach inherits five
things that Phases 0–6 already built and tested, and that are the expensive parts
to get right:

| Inherited | Built in | What Kavach adds |
|-----------|----------|------------------|
| Normalized event model with mandatory provenance | Phase 0 | Security event classes; `v1` schema migration |
| Topology graph in Postgres, blast-radius traversal at p99 18.3ms | Phase 1 | Threat entities on the same graph — actors, malware, CVEs, techniques |
| Detection with robust baselines and an evaluation harness | Phase 2 | Security-specific detectors, scored on the same harness |
| Correlation gated by adjacency **and** time | Phase 2 | Campaign-level correlation across a kill chain |
| Dharma policy engine, guarded execution, append-only audit | Phase 0/3 | Containment actions — isolate, block, revoke — under the same verdict rule |

The commercial and research argument for Kavach rests on that inheritance. A
Blue Team agent that can isolate a host is only responsible if something already
stops it from isolating the wrong one, records why it tried, and checks whether
it worked. Pashupatastra built that constraint first. Kavach is what it was for.

**The corollary is a sequencing rule, and it is not advisory:** no Kavach phase
starts before its Phase 0–6 dependency has met its exit criterion. Building the
Blue Team agent on an unverified detection layer produces a system that acts
confidently on noise, which is worse than no system.

---

## The research question

> Can a domain-specific architecture combining security telemetry, threat
> intelligence, a security knowledge graph, long-term incident memory,
> retrieval-grounded reasoning, and a policy-constrained Blue Team agent improve
> threat detection, investigation, and defensive decision-making compared with
> conventional security analytics and a general-purpose LLM?

The claim must be a measurement. Phase 12 is where it becomes one; every phase
before it exists to make that measurement possible and honest.

### Hypotheses, and where each is tested

| # | Hypothesis | Tested in | Baseline it must beat |
|---|-----------|-----------|----------------------|
| H1 | Threat-intelligence enrichment improves contextual classification | Phase 9 | Same detector, enrichment disabled |
| H2 | ATT&CK grounding improves adversary-behavior classification | Phase 9 | LLM asked to map without the graph |
| H3 | Long-term memory improves recurring-incident investigation | Phase 10 | Same agent, Smriti retrieval disabled |
| H4 | Retrieval grounding reduces unsupported security claims | Phase 9 | Ungrounded LLM, same prompts |
| H5 | Graph reasoning improves entity-relationship accuracy | Phase 8 | Vector retrieval alone |
| H6 | Human + Kavach beats human alone on Blue Team tasks | Phase 12 | Human with standard SIEM |
| H7 | A policy-constrained agent automates low-risk response with fewer unsafe actions | Phase 11 | Naive LLM agent, tools, no policy layer |
| H8 | The system generalizes to held-out attack families | Phase 12 | Trained-on-all control |
| H9 | Intel updates improve awareness without retraining | Phase 12 | Frozen-intel control |

**H4, H7 and H8 are the ones that can fail and still be worth publishing.** A
null result on H4 in particular would be a real contribution: it would say
grounding is insufficient, not merely unhelpful. Design the experiments so a null
result is reportable rather than embarrassing, or the benchmark becomes theater.

---

## Workstream A — Literature review *(runs from now, not a phase)*

The research gap must be established before the architecture is defended, not
after. This runs in parallel with Phases 7–8 and gates the paper, not the code.

- [ ] Systematic review across: AI-driven intrusion detection, cyber threat
      intelligence, security LLMs, agentic AI for security operations, RAG for
      security, cybersecurity knowledge graphs, autonomous cyber defense,
      human-AI teaming, adversarial ML, and security AI evaluation
- [ ] Primary sources only — IEEE, ACM, USENIX, NIST, MITRE, CISA, arXiv, and
      official dataset publications. Vendor whitepapers may be cited as evidence
      of practice, never as evidence of performance
- [ ] Structured extraction per paper: claim, dataset, baseline, metric,
      limitation. Stored as data in `docs/research/`, not prose
- [ ] Gap statement — written as what *has not been measured*, not as what has
      not been built. "No one combined X and Y" is not a research gap
- [ ] Related-work section drafted before Phase 9 freezes the method

**Risk:** the review becomes a bibliography instead of an argument. Mitigation —
the deliverable is the gap statement, and it is one paragraph.

---

## Phase 7 — Security Data Foundation · Weeks 25–28

**Goal:** security telemetry and threat intelligence enter the platform under the
same provenance discipline as everything else.

**Depends on:** Phase 1 exit criterion.

### 7.1 Event model v1

- [ ] Security event classes added to the core model — authentication, process
      execution, network flow, file integrity, detection alert
- [ ] Schema migration `v0 → v1` under the additive rules in [adr/Schema](adr/Schema.md)
- [ ] Round-trip and quarantine tests at parity with the v0 suite
- [ ] `packages/core` still imports no AWS and no vendor SDK — *evidence: CI gate holds*

### 7.2 Security connectors (Drishti extension)

- [x] CloudTrail — mutating and security-relevant API calls *(built in Phase 1; live verification still needs AWS credentials)*
- [ ] Endpoint telemetry — Sysmon / eBPF process and network events
- [ ] Authentication logs — identity provider and OS auth
- [ ] Network detection — Zeek and Suricata
- [ ] EDR/SIEM alert ingestion that **defers** to upstream rules rather than seconding them, reusing the Phase 2 deferral rule
- [ ] Read-only by construction — no security connector exposes a mutating method

### 7.3 Threat intelligence ingestion (Drishti — the intel plane)

- [ ] CVE / NVD, with CVSS and CWE linkage
- [ ] CISA Known Exploited Vulnerabilities
- [ ] MITRE ATT&CK, **version-pinned** — every mapping and every experiment
      records the ATT&CK version it was produced against, because the taxonomy
      moves and an unversioned mapping is unreproducible a year later
- [ ] STIX/TAXII and MISP-compatible feed ingestion
- [ ] Vendor advisories and public threat reports
- [ ] Per-record provenance: source, retrieval time, license, confidence, feed version

### 7.4 Intel is data, never instruction

- [ ] Threat-intel text passed to any model is quoted as data, extending the
      Phase 1 OpenSearch rule — *evidence: injection corpus in the test suite*
- [ ] Ingested intel lands **untrusted** and cannot enter long-term memory
      without a validation step. A feed is an input, not an authority
- [ ] Feed poisoning test — a hostile indicator must not reach an action path

### 7.5 Data quality as a research object

- [ ] Deduplication, label normalization, and taxonomy mapping across sources
- [ ] Quality score per record, and per feed
- [ ] Documented analysis of class imbalance, label noise, and **temporal
      leakage** — the failure mode that most often inflates published IDS results
- [ ] Dataset cards for every corpus used

**Exit criterion:** a single normalized stream carries host, network, identity,
cloud and intel records; every record resolves to an entity or is visibly
quarantined; the injection corpus passes.

**Risk:** connector sprawl, exactly as in Phase 1. Mitigation — endpoint and
authentication only until the ATT&CK mapping in Phase 9 is trusted.

---

## Phase 8 — Security Knowledge · Weeks 29–33

**Goal:** security knowledge becomes a queryable graph rather than a document pile.

**Depends on:** Phase 7, and the Phase 1 graph.

### 8.1 Ontology

- [ ] Unified entity types — Threat Actor, Campaign, Malware, CVE, CWE, CAPEC,
      Technique, Tactic, Indicator, Asset, Detection, Mitigation, Incident
- [ ] Relationship types with defined semantics — `uses`, `implements`,
      `targets`, `affects`, `detected_by`, `mitigated_by`
- [ ] Mapped onto the existing `EntityRef` namespace so an asset in the security
      graph and an asset in the topology graph are **the same node**, not two
- [ ] Ontology versioned like a schema, with an ADR for breaking changes

### 8.2 Knowledge graph

- [ ] Built on the Phase 1 Postgres graph store — *revisit only if a measurement,
      not an instinct, says Postgres has stopped being enough, per [adr/Graph](adr/Graph.md)*
- [ ] Edges from asserted intel or observed telemetry only — **never from
      co-occurrence**, the Phase 1 rule that keeps the graph from inventing causality
- [ ] Every edge carries source and confidence; a low-confidence edge is
      traversable but must be reported as such
- [ ] Query performance benchmarked against a stated target, as the topology
      graph was — *evidence: extended `scripts/benchgraph.py`*

### 8.3 Queries it must answer

- [ ] "What actors are associated with this malware?"
- [ ] "What techniques does this incident exhibit?"
- [ ] "Which of *our* assets are exposed to this CVE?" — the join between public
      intel and private topology, and the query with the most product value
- [ ] "What mitigations address this technique, and do we have them?"
- [ ] "What historical incidents resemble this one?"

### 8.4 ATT&CK integration

- [ ] Evidence → behavior → technique → tactic → detection → mitigation chain,
      each link citing what supports it
- [ ] Coverage view — which techniques our telemetry could detect, and which we
      are **blind to**. The blind list is the more useful half and must not be
      cosmetically minimized
- [ ] Mapping accuracy measured against a hand-labelled set before it is trusted
      anywhere downstream

**Exit criterion:** all five queries in 8.3 answered from the graph within a
stated latency budget; ATT&CK mapping accuracy reported with a confidence
interval on a held-out labelled set.

**Risk:** an ontology designed for completeness rather than for the queries.
Mitigation — 8.3 is written before 8.1 is implemented, and prunes it.

---

## Phase 9 — Detection, Grounding, Memory · Weeks 34–39

**Goal:** the system produces defensible security findings, not plausible ones.

**Depends on:** Phase 2 exit criterion and its unresolved seasonality gap.

### 9.1 Security detection

- [ ] Security detectors built on the Phase 2 evaluation harness, scored by the
      same measures — precision, episode recall, lead time, false alarms per 1000
- [ ] **The Phase 2 seasonality gap must close before this starts.** Robust-z
      scores 859 false alarms per 1000 on a daily-shaped series against EWMA's 43.
      Human activity is the most seasonal signal in the building; shipping a
      security detector on that baseline would generate an alert every workday
      morning and teach operators to ignore it
- [ ] Rare-event detection where the positive class is a fraction of a percent —
      accuracy is meaningless here and PR-AUC is reported instead
- [ ] ML detection **only if** it beats the best statistical strategy on the
      benchmark, keeping the Phase 2 rule that the choice is a measurement

### 9.2 Kill-chain correlation

- [ ] Findings correlated into campaign-level incidents across a kill chain,
      extending Phase 2 correlation with attacker-progression ordering
- [ ] Unknown relationships still default to **separate** incidents — a
      fabricated kill chain is more damaging than a split one, because it reads
      as a coherent story and gets acted on
- [ ] Incorrect-merge rate reported separately from incorrect splits

### 9.3 RAG and the AI Gateway

- [ ] Built on the Phase 2.3 AI Gateway — vendor-neutral, structured outputs,
      token accounting. **No direct provider SDK calls from engine code**
- [ ] Retrieval over the knowledge graph and the intel corpus, hybrid with
      structured entity filters
- [ ] Every security claim cites its evidence; unsupported claims are
      **suppressed**, not surfaced with low confidence
- [ ] Hallucination and citation-accuracy measured on a held-out question set —
      this is H4, and the measurement is the deliverable

### 9.4 Smriti — security memory

- [ ] Episodic: prior incidents, analyst decisions, confirmed false positives
- [ ] Semantic: the knowledge graph
- [ ] Procedural: runbooks and approved response playbooks
- [ ] Organizational: environment topology, owners, security policy
- [ ] "We have seen this before" surfaced with the prior incident and its outcome
- [ ] Every memory carries source, timestamp, confidence, owner, retention policy
- [ ] **Tenant isolation from the first commit**, not retrofitted — global
      knowledge (ATT&CK, CVE, public intel) and tenant knowledge (telemetry,
      incidents, decisions) are separate stores with separate access paths
- [ ] Private telemetry never trains a global model — *evidence: an explicit
      test, not a policy document*

**Exit criterion:** on 30 hand-labelled historical security incidents, the top-1
technique attribution is correct ≥70% of the time and every claim cites its
telemetry; the ungrounded-LLM control is run on the same set and reported beside it.

**Risk:** a fluent, wrong incident narrative. Mitigation — the evidence
requirement is a validator, as it is in Buddhi, not a guideline.

---

## Phase 10 — Blue Team Agents · Weeks 40–45

**Goal:** the system investigates and responds, and cannot act outside its bounds.

**Depends on:** Phase 3 agent runtime and real executors.

### 10.1 Sati — the agent

**Sati** is the AI agent: the reasoning actor that uses Drishti, Buddhi, Smriti
and Astra rather than being one of them. It ships as one identity with
specialised roles, not as three products.

- [ ] **`sati.sentinel`** — triage. Alert to finding, with a disposition and a reason
- [ ] **`sati.hunter`** — hypothesis-driven hunting. Returns hypothesis, queries,
      findings, ATT&CK mapping, confidence, and next step
- [ ] **`sati.analyst`** — incident reconstruction: timeline, kill-chain hypotheses
      per stage, affected assets, evidence, risk, recommended response, and
      **stated uncertainty**
- [ ] Each declared as an `AgentSpec` with tools, budget and risk ceiling; the
      Phase 0 least-privilege guarantee applies unchanged
- [ ] Orchestration through the Phase 3 runtime — no new agent framework

### 10.2 Containment under Dharma

Response actions register in the existing action registry with risk, expected
post-state and rollback. No new execution path is created; that is the point.

| Action | Disposition |
|--------|-------------|
| Read logs, query intel, query graph, generate report | Allow |
| Enrich indicator, open ticket, notify | Allow |
| Isolate host, disable account, block indicator | Human approval required |
| Delete artifact, execute arbitrary command | Denied by default, in every environment |

- [ ] Every containment action has a **tested rollback** — an isolation that
      cannot be lifted is an outage the platform caused
- [ ] Blast radius computed from the topology graph, so isolating a host states
      what depends on it *before* an approver decides
- [ ] Dry-run default and per-environment live opt-in, inherited unchanged
- [ ] Autonomy tiers reviewed for the security context — the Phase 0 thresholds
      were calibrated for operations and must be re-argued here, not assumed

### 10.3 Audit and safety

- [ ] Evidence trail per decision: inputs, retrieved evidence, sources, tool
      calls, decision summary, confidence, policy verdict, action, approver,
      result, verification. **No private chain-of-thought is stored**
- [ ] Prompt-injection defense across telemetry, intel, and attacker-controlled
      log content — *evidence: an adversarial corpus, refreshed each phase*
- [ ] Excessive-agency test: no path reaches an executor without a recorded verdict
- [ ] **Automation-bias measurement** — how often approvers accept without
      inspecting, extending the Phase 3 rubber-stamp guard. An approval rate near
      100% means the policy layer is decorative

**Exit criterion:** a red-team pass finds no path to a containment action without
a policy verdict; every containment action has a tested rollback; the audit trail
reconstructs every decision end to end.

**Risk:** this is where the project can cause a real outage or lock out a real
user. Mitigation — dry-run default, per-environment opt-in, blast-radius
escalation regardless of score, and no destructive permission granted to any role.

---

## Phase 11 — Cyber Range · Weeks 46–51

**Goal:** controlled, repeatable attack telemetry — generated legally, in an
environment we own.

### 11.1 Range

- [ ] Isolated environment built from the Phase 0 compose stack — no route to any
      third-party network, enforced at the network layer rather than by intent
- [ ] Instrumented: Zeek, Suricata, Sysmon, auth and cloud logs
- [ ] Provisioned per run and torn down after, matching the Phase 5 harness

### 11.2 Red — controlled adversary emulation

- [ ] Scenario library from public ATT&CK-mapped emulation plans
- [ ] Scenarios are **declarative and versioned**, so a run is reproducible
- [ ] Purpose is telemetry generation and detection evaluation. This is not an
      offensive capability and must not become one — no autonomous exploitation,
      no target outside the range, no credential harvesting beyond synthetic accounts
- [ ] Ethics and authorization boundary recorded as an ADR before the first run

### 11.3 Red vs Blue

- [ ] Scenario → telemetry → detection → investigation → response → score
- [ ] **Negative scenarios** — benign activity that resembles an attack, where
      the correct answer is to do nothing. Without these the benchmark rewards
      paranoia
- [ ] **Escalation scenarios** — where the correct answer is to hand off
- [ ] All scenarios authored **before** the logic that resolves them

**Exit criterion:** the range provisions from one command, runs a scenario, and
produces labelled telemetry that the detection layer consumes without manual
intervention.

**Risk:** simulated attacks are cleaner than real ones, and detection tuned on
them overfits. Mitigation — stated as a threat to validity in the paper, and
partially answered by evaluating against public real-world corpora alongside.

---

## Phase 12 — Benchmark, Studies, Release · Weeks 52–60

**Goal:** claims become numbers, with error bars.

### 12.1 PSB — Pashupatastra Security Benchmark

- [ ] Extends the Phase 5 PIB harness rather than replacing it
- [ ] 100+ scenarios across attack families, including negative and escalation cases
- [ ] N runs per scenario; variance reported
- [ ] One-command reproducibility, runnable by a third party on release day

### 12.2 Arms

- [ ] Human analyst with a standard SIEM
- [ ] Signature and rule-based detection
- [ ] Classical ML — random forest, gradient boosting, LSTM
- [ ] General-purpose LLM, ungrounded
- [ ] General-purpose LLM with generic RAG
- [ ] Kavach, full architecture

### 12.3 Ablations

Each removes one component and re-runs, isolating its contribution:

- [ ] Without threat-intel enrichment *(H1)*
- [ ] Without ATT&CK grounding *(H2)*
- [ ] Without Smriti retrieval *(H3)*
- [ ] Without evidence-citation enforcement *(H4)*
- [ ] Without graph reasoning, vector retrieval only *(H5)*
- [ ] Without policy tiers *(H7)*

### 12.4 Generalization

- [ ] **Held-out attack family** — trained and tuned without it, evaluated on it *(H8)*
- [ ] **Temporal split** — trained on older data, evaluated on newer, which is
      the only split that reflects deployment. Random splits leak *(H9)*
- [ ] Frozen-intel control, isolating intel updates from model changes *(H9)*
- [ ] Drift monitoring with alerts when performance degrades

### 12.5 Human-AI study

- [ ] Group A human only, Group B Kavach only, Group C human + Kavach *(H6)*
- [ ] Pre-registered protocol and analysis plan — written before data collection
- [ ] Institutional review obtained before recruiting — **blocked: needs a human
      decision and a university process**
- [ ] Measured: time to detect, time to investigate, accuracy, false positives
      and negatives, technique-mapping accuracy, evidence quality, MTTR
- [ ] Underpowered results reported as underpowered. With a small participant
      pool this study describes rather than proves, and must say so

### 12.6 Reporting

- [ ] Metrics computed from the audit log alone, per [research/METRICS.md](research/METRICS.md)
- [ ] **False-positive and missed-detection rates reported before detection rate**
- [ ] Confidence intervals and effect sizes, not point estimates
- [ ] Confidence calibration — a stated 90% confidence should be right about 90%
      of the time, and if it is not, that is a finding
- [ ] Per-scenario results published, not only aggregates; any excluded scenario
      states its reason in the table
- [ ] Error analysis — what the failures have in common

### 12.7 Paper and release

- [ ] Draft — *Kavach: Policy-Constrained Autonomous Cyber Defense with Grounded
      Security Reasoning*
- [ ] Threats to validity stated plainly, including the self-authored benchmark,
      range realism, and participant count
- [ ] Open source: schemas, connectors, evaluation harness, benchmark, SDK
- [ ] Commercial: enterprise connectors, managed intel, tenant memory, premium models
- [ ] Vulnerability disclosure process published before any public release

**Exit criterion:** the full benchmark runs reproducibly from one command and
produces the metrics table, ablations, and generalization results.

---

## Deployment track *(continuous, not a phase)*

Unchanged from [DEPLOYMENT.md](DEPLOYMENT.md), with the split preserved:

```
Browser → Vercel (Next.js) → API (private) → AWS: services, data, models
```

- [ ] Vercel serves frontend only. No AI infrastructure, no data plane, no
      direct database reachability from the edge
- [ ] AWS: private subnets, IRSA per agent, Secrets Manager and KMS for every
      credential, CloudTrail in all accounts, budget alarms
- [ ] Bedrock reached through the AI Gateway, never directly from engine code
- [ ] Cost per investigation, per experiment and per training run tracked as
      first-class metrics — this is a research project and an unbounded inference
      bill ends it faster than any technical problem
- [ ] Name clearance from Phase 0.10 clears **before** any public launch. It is
      still open, and it gates the domain, the org, and the paper's title page

---

## What must not be claimed

The [ROADMAP.md](ROADMAP.md) golden rule applies with more force here, because
security claims get bought on trust and audited later:

> Every claim is backed by data, an experiment, a metric, evidence, and a stated
> limitation.

Specifically, and without exception:

- An AI assessment is never labelled a confirmed attack. Verification states are
  `reported`, `observed`, `corroborated`, `confirmed`, `suspected`, `predicted` —
  and a model produces at most `suspected`
- Model confidence is not truth. A defensible decision is assessment + evidence +
  source + confidence + verification
- "Autonomous", "faster", "more accurate" appear only next to the experiment that
  measured them

---

## Dependency map

```
Phase 1 (Drishti)  ──────────► Phase 7 (security data)
Phase 1 (graph)    ──────────► Phase 8 (knowledge graph)
Phase 2 (detection, harness) ► Phase 9 (security detection)   ◄── seasonality gap must close
Phase 2 (AI Gateway) ────────► Phase 9 (RAG, grounding)
Phase 3 (agent runtime) ─────► Phase 10 (Blue Team agents)
Phase 0 (Dharma, audit) ─────► Phase 10 (containment)
Phase 4 (verification) ──────► Phase 10 (did containment work)
Phase 5 (PIB harness) ───────► Phase 11 (range) ──► Phase 12 (PSB)
Workstream A (literature) ───────────────────────► Phase 12 (paper)
```

The two hard gates: **the Phase 2 seasonality gap blocks Phase 9**, and **Phase 3
executors block Phase 10**. Everything else can slip without corrupting a result.
