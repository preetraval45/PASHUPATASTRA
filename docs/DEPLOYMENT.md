# Deployment — AWS

**Status:** Planned. Terraform lands in Phase 0.5 (data layer) and Phase 3
(execution IAM). Target platform decided in
[the Platform ADR](adr/Platform.md).

## Split: Vercel for the dashboard, AWS for the platform

The Next.js dashboard deploys to **Vercel**; everything with state, credentials,
or execution authority stays on **AWS**.

```
   Operators ──► Vercel (apps/web, Next.js)
                     │  HTTPS, NEXT_PUBLIC_API_URL
                     ▼
                 AWS: ALB ──► EKS ──► RDS / ElastiCache / OpenSearch / S3
```

This works because the dashboard holds no authority. It renders what the API
reports and never computes risk, tier, or verification outcome itself — a second
implementation in the browser would be a second source of truth (the Grounding ADR).
Policy evaluation, execution, and audit are all server-side on AWS.

Consequences:

- The dashboard is a public-internet client of the API. It gets no AWS
  credentials, ever — `NEXT_PUBLIC_*` variables are visible to anyone who loads
  the page, so nothing secret may go there.
- The API needs an authenticated, CORS-scoped public endpoint. `cors_origins` is
  set per environment; a wildcard is never acceptable.
- On-prem customers run the dashboard themselves from the same container as the
  API. Vercel is a convenience for the hosted product, not a dependency of it.

## Topology

```
                          ┌────────────────────────────┐
   Operators ──► CloudFront ──► ALB ──► EKS            │
                          │      ┌──────┴──────┐        │
                          │      │  web (Next) │        │
                          │      │  api (FastAPI)       │
                          │      │  workers    │        │
                          │      └──────┬──────┘        │
                          │             │               │
                          │   ┌─────────┼─────────┐     │
                          │   ▼         ▼         ▼     │
                          │  RDS    ElastiCache  Open-  │
                          │  Postgres  Redis     Search │
                          │   │                         │
                          │   ▼                         │
                          │  S3  (artifacts, snapshots) │
                          └────────────────────────────┘
                                       │
                   ┌───────────────────┼───────────────────┐
                   ▼                   ▼                   ▼
              Bedrock             Secrets Mgr          CloudTrail
            (AI Gateway)          + KMS               (audit mirror)
```

Ingestion runs asynchronously so a telemetry spike cannot stall the reasoning
loop:

```
AMP / OpenSearch / EKS API / CloudTrail / GuardDuty
        │
        ▼
   Drishti connectors ──► SQS ──► normalization workers ──► core event store
                                                   │
   EventBridge (scheduled verification windows) ───┘
```

## Service mapping

| Layer | AWS | Self-hosted equivalent (on-prem path) |
|-------|-----|----------------------------------------|
| Compute | EKS | Any conformant Kubernetes |
| Primary DB | RDS PostgreSQL Multi-AZ | PostgreSQL |
| Cache / queues | ElastiCache Redis | Redis |
| Search | OpenSearch Service | Elasticsearch / OpenSearch |
| Objects | S3 | MinIO |
| Metrics | Amazon Managed Prometheus | Prometheus |
| Dashboards | Amazon Managed Grafana | Grafana |
| Models | Bedrock | Direct provider APIs via AI Gateway |
| Secrets | Secrets Manager + KMS | Vault / sealed secrets |
| Async | SQS + EventBridge | Redis queues + cron |
| Audit mirror | CloudTrail | Append-only Postgres only |

Every AWS choice has a working self-hosted counterpart. That is the constraint
that keeps the on-prem wedge open — a managed feature with no equivalent gets
rejected unless the on-prem path is explicitly given up for that capability.

## Two deployment targets

1. **`infra/terraform/`** — AWS managed. Production, staging, and the benchmark
   environment.
2. **`infra/docker/`** — docker-compose. Local development, the reference stack
   the benchmark injects faults into, and the seed of the on-prem distribution.

Both are maintained from Phase 3 onward. CI runs the benchmark against the
compose stack, so a broken on-prem path fails the build rather than being
discovered at the first enterprise deal.

## IAM — the floor beneath Dharma

Dharma is the policy layer. IAM is the floor beneath it. If Dharma has a bug,
IAM still bounds the damage — two independent layers, per
[the Platform ADR](adr/Platform.md).

- One IRSA role **per agent**, matching its declared permissions in
  [specs/Agent Spec.md](specs/Agent%20Spec.md). An agent with
  `modify_database: false` has no RDS-modify permission in IAM either.
- **Read and write roles are separate.** Perception credentials cannot mutate
  anything, which makes Drishti incapable of causing an incident.
- Destructive permissions (`rds:DeleteDBInstance`, `ec2:TerminateInstances`, and
  peers) are **not granted to any Pashupatastra role**, in any environment. They
  are permanently outside autonomy per
  [specs/Policy Model.md](specs/Policy%20Model.md), so granting them would only
  create risk without capability.
- Per-environment account separation: dev, staging, prod. Production execution
  credentials are unreachable from lower environments.
- All connector credentials live in Secrets Manager, KMS-encrypted, rotated. None
  in environment files or images.

## CloudTrail as independent verification

CloudTrail records what AWS actually executed, independent of the audit trail
Pashupatastra writes about itself. That gives the benchmark something rare — an
out-of-band check on whether the system's account of its own actions is true.
Divergence between the internal audit log and CloudTrail is a reportable defect,
and the reconciliation is a result worth publishing.

## Kavach inputs

AWS-native security telemetry is high-signal and cheap to connect: GuardDuty
findings, CloudTrail management events, Security Hub, IAM Access Analyzer, VPC
flow logs, Inspector. These feed the `security` event class in
[specs/Event Model.md](specs/Event%20Model.md) and are correlated with
infrastructure and application events rather than being read in isolation.

Kavach remains detection and correlation only — remediation authority runs
through Dharma like any other action.

## Cost control

Benchmark runs are the dominant cost driver: hundreds of scenarios × N runs each
× a live stack per run.

- Benchmark environment is ephemeral — provisioned per run, torn down after
- Graviton instances and Spot for benchmark and worker nodes
- Bedrock usage metered per scenario; token budgets in the agent spec are cost
  ceilings as well as safety ceilings
- Cost per resolved incident is tracked as a product metric, not just a bill —
  an autonomous fix that costs more than the outage is not a fix

## Open questions

- Aurora PostgreSQL vs. RDS PostgreSQL — Aurora's failover and read scaling
  matter only at a volume that does not exist yet. RDS until it does.
- Whether the topology graph lives in Postgres with recursive CTEs or a dedicated
  store (Neptune). Deferred to Phase 1 pending real query shapes.
- Bedrock model availability by region versus where customer telemetry may
  legally reside.
