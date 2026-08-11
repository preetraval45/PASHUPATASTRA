# Architecture

## The loop

Every subsystem exists to serve one cycle:

```
Observation → State Reconstruction → Causal Inference → Risk Assessment
   → Action Planning → Policy Evaluation → Approval → Execution
   → Verification → Learning
```

Nothing skips a stage. A stage that cannot complete fails the cycle rather than
degrading into a guess.

## Layering

```
                    PASHUPATASTRA
                         ▲
                         │   intelligence + control
        ┌────────────────┼────────────────┐
        │                │                │
   Prometheus       Elasticsearch      OpenTelemetry
      metrics            logs             traces
```

Pashupatastra consumes existing observability. It does not reimplement
collection, storage, or a TSDB.

## Subsystems

### Drishti — Perception
Connectors pull from Prometheus, OpenTelemetry, Elasticsearch, Docker,
Kubernetes, cloud APIs, CI/CD, and security tooling. Everything is normalized
into one event model carrying source, timestamp, entity reference, and
provenance. Drishti also maintains the topology graph.

### Smriti — Memory
Append-only organizational memory: past incidents, applied fixes, architecture
snapshots, deployments, config changes, dependencies, failures, engineering
decisions, runbooks. Retrieval is hybrid — embeddings over incident narratives
plus structured filters over entities and symptoms. Verification outcomes feed
back here; this is the learning signal.

### Buddhi — Reasoning
Combines LLM reasoning, structured tool calls, retrieval, causal graphs,
anomaly detection, and deterministic rules. Produces hypotheses with confidence
scores and evidence citations. **The LLM is not the source of truth** — an
unsupported hypothesis is suppressed, not surfaced.

### Knowledge graph
Infrastructure as a typed graph:

```
User → Frontend → API → { Redis, PostgreSQL → Storage }
```

Enables dependency traversal, impact propagation, and blast-radius computation:
if PostgreSQL degrades, which services, which users, how many.

### Astra — Action engine
`ASTRA = Autonomous System Tactical Response Architecture`. Decides whether to
act, which action, at what risk, with what expected outcome and what rollback.
Every registered action declares:

```yaml
action: rollback_deployment
risk: 45
expected_post_state: { error_rate: "<1%", db_connections: "<70%" }
rollback: redeploy_previous
blast_radius: computed
```

### Dharma — Policy engine
Risk tiers govern authority:

| Risk | Authority |
|------|-----------|
| 0–30 | Autonomous |
| 31–60 | Approval required |
| 61–80 | Senior approval |
| 81+ | Never autonomous |

Blast radius above threshold escalates regardless of risk score. Astra cannot
execute without a Dharma verdict — enforced structurally, not by convention.

### Kavach — Security
Detects unexpected SSH logins, unusual API traffic, privilege escalation,
container anomalies, unknown processes, credential misuse, suspicious
deployments, unexpected egress. Correlates security + infrastructure +
application events into a single judgment: attack or operational failure.

### Kaal — Simulation
Digital twin of customer infrastructure. Answers "what happens if…" before
execution: expected downtime, affected services, users impacted, recovery
probability.

## Agents

Each agent is scoped, not omnipotent:

```yaml
agent:
  name: database-responder
permissions:
  read_metrics: true
  read_logs: true
  restart_service: true
  modify_database: false
risk_limit: 40
approval:
  required_above: 40
```

MVP topology — one orchestrator plus three specialists (Incident,
Infrastructure, Security). The full Commander → SRE/Security/DB/DevOps/Network/
Cloud fleet comes later, and only once the policy layer is proven.

## Services

```
API Gateway
  ├── Incident Engine
  ├── Agent Engine
  ├── Reasoning Engine     (Buddhi)
  ├── Policy Engine        (Dharma)
  ├── Action Engine        (Astra)
  ├── Knowledge Engine     (Smriti + graph)
  └── Audit Engine
```

## Data

| Store | Role | AWS |
|-------|------|-----|
| PostgreSQL | Incidents, actions, policies, audit, topology | RDS Multi-AZ |
| Redis | Cache, queues, short-lived agent state | ElastiCache |
| Elasticsearch | Logs, events, search | OpenSearch Service |
| Object storage | Incident artifacts, reports, snapshots | S3 |

AWS is the target deployment platform ([the Platform ADR](adr/Platform.md)),
but **`packages/core` contains no AWS types**. The domain model runs on a laptop;
managed services are a deployment concern. Full topology in
[DEPLOYMENT.md](DEPLOYMENT.md).

## AI Gateway

All model access flows through one abstraction: provider-neutral, structured
outputs (validated Pydantic schemas), embeddings, RAG, agent orchestration, and
an evaluation harness. Engine code never imports a vendor SDK directly. Bedrock
is the primary provider on AWS; direct provider APIs remain viable behind the
same interface.

## Dashboard

```
/overview  /incidents  /infrastructure  /services  /agents
/actions   /security   /knowledge      /audit     /settings
```

## Non-goals

- Replacing Prometheus, Grafana, Elasticsearch, or OpenTelemetry
- Giving an LLM unmediated shell or cloud-credential access
- Autonomous execution of destructive infrastructure operations, ever
- Free-text model output as a control signal
