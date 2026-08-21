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

## The demo tier

A third target, and the only one currently running: a public dashboard carrying
scripted scenarios. It exists so the interface can be looked at, not so anything
can be operated.

```
   Anyone ──► Vercel (apps/web)
                  │  HTTPS, NEXT_PUBLIC_API_URL
                  ▼
              AWS Lambda (services/api, zip archive)
                  │
                  └─ DynamoDB, one table; no RDS, no VPC, no ECR
```

Built by `scripts/buildlambda.py` and deployed by `scripts/deploylambda.py`.
What it deliberately omits is the point: no VPC and therefore no NAT gateway, no
container registry, and no database. That keeps it inside the always-free
allowance rather than the twelve-month one, and it is why it must never be
pointed at anything real.

What that costs in honesty, stated where the deployment can be seen rather than
only here:

- `/health` reports whichever store actually answered. `audit_storage: memory`
  forces `status: degraded`, because an audit trail that does not survive a
  restart is not an audit trail, and the dashboard renders that verdict rather
  than hiding it. With the table configured it reads `ok · dynamodb`.
- The scenarios are scripted. Durable state makes the console consistent between
  cold starts; it does not make anything on it real.
- Both execution gates are shut — `PASHU_DRY_RUN=true`, and the environment is
  absent from `PASHU_LIVE_ENVIRONMENTS`. A misconfiguration fails closed into
  dry-run rather than open (SECURITY.md, control 1).
- The model provider is `echo`, the deterministic stub. Reasoning output is not
  a model's, and `/health` says `configured: false` so nobody has to infer that
  from suspiciously empty text.

The topology and event history come from `app/seed.py`, which replays the
labelled corpus in `benchmark/incidents/`. Every seeded event keeps
`source_system="scenario"` in its provenance; the seed invents no dependencies
beyond the two the demo incident already asserts, and no user counts at all. A
blast radius of zero users is visibly wrong to a reader, which is the point — an
invented one would not be.

### One table, several namespaces

DynamoDB's always-free allowance is 25 capacity units per **account**, not per
table, so a second table for local work would take capacity away from the
deployed console rather than add any. `PASHU_DYNAMO_NAMESPACE` prefixes every
partition key instead, and one table holds `prod` and `test` without either
seeing the other.

Set it to something other than `prod` for anything that is not the deployment.
The default is `prod` deliberately — a deployment that forgets to set it still
finds its own data, where a machine-specific default would hand the Lambda an
empty console after a redeploy.

This is not housekeeping. Before the namespace existed, a local run seeded the
*infrastructure* demo incident into the security console, and a test run put
four fixture hosts on the live service map. In memory both would have gone at
the next restart; in a table they stayed until they were deleted by hand.
`scripts/cleardynamo.py` is that hand — it deletes nothing without `--yes`.

> **Function URLs may be blocked.** Some accounts refuse anonymous invocation of
> a Lambda Function URL: the resource policy is correct, `AuthType` is `NONE`,
> and AWS still answers 403 before the request reaches the function. A signed
> SigV4 request to the same URL succeeds, which is how to tell this apart from a
> broken deployment. `scripts/deployapigateway.py` puts an HTTP API in front as
> the way around it.

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

## Getting authenticated

The AWS CLI and Terraform are installed. What is missing is credentials, and
this is the one part that cannot be automated on your behalf.

**An IAM console username and password cannot be used by the CLI or SDK.** They
authenticate a browser session only. Programmatic access needs one of:

```sh
# Preferred: short-lived credentials, nothing static on disk
aws configure sso

# Or, if the account has no Identity Center yet: create an access key in the
# IAM console, then enter it at this prompt — never paste it into a chat window
aws configure
```

Verify with:

```sh
aws sts get-caller-identity
```

Then provision the database:

```sh
cd infra/terraform
terraform init -backend-config=envs/dev.backend.hcl
terraform apply -var-file=envs/dev.tfvars
```

The master password is generated by Terraform and written to Secrets Manager. It
is never placed in a variables file, an environment file, or terminal output.

Point the API at it by resolving the secret at runtime rather than copying the
value:

```sh
export PASHU_DATABASE_URL=$(aws secretsmanager get-secret-value   --secret-id pashupatastra/dev/database   --query SecretString --output text | python -c "import json,sys; print(json.load(sys.stdin)['url'])")

cd services/api && python -m app.migrate
```

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
