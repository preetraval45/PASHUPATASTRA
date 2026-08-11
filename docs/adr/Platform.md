# AWS as the target platform

- **Status:** Accepted
- **Date:** 2026-08-10
- **Phase:** Phase 0

## Context

The stack named in the founding plan — PostgreSQL, Redis, Elasticsearch, object
storage, Prometheus, Kubernetes — is deliberately generic. Every one of those has
a managed AWS equivalent, and running them unmanaged during a 24-week build means
spending the build on operations rather than on the thesis.

There is a real tension. [ROADMAP.md](../ROADMAP.md) positions on-prem and hybrid
deployment as the commercial wedge, because it is underserved relative to
cloud-native and because the policy/audit story sells hardest to customers who
cannot send telemetry outside their boundary. A build that hard-codes AWS into
the domain model forecloses exactly that market.

## Decision

**AWS is the target deployment platform. It is not a dependency of the domain
model.**

The line is drawn at the package boundary:

- `packages/core` — event model, incident model, policy engine, agent framework.
  **Zero AWS imports.** No `boto3`, no ARNs in schemas, no assumption of a cloud.
  This is the future open-source package and must run on a laptop.
- `packages/connectors` — AWS-specific readers behind the same connector
  interface as Prometheus and Kubernetes. AWS is one source among several.
- `services/api`, `infra/` — AWS-native. Managed services, IAM, Terraform.

Managed services chosen over self-hosted for V1:

| Need | AWS service | Why |
|------|-------------|-----|
| Compute | EKS | Kubernetes is already the connector target; on-prem parity via any conformant cluster |
| Primary DB | RDS PostgreSQL (Multi-AZ) | Audit trail must survive an AZ loss |
| Cache / queues | ElastiCache Redis | Agent state, short-lived queues |
| Log & event search | OpenSearch Service | Elasticsearch-compatible; connector code is portable |
| Object storage | S3 | Incident artifacts, snapshots, benchmark results |
| Metrics | Amazon Managed Prometheus (AMP) | Drop-in for the Prometheus connector |
| Dashboards | Amazon Managed Grafana (AMG) | Operator-facing observability, not the product UI |
| Model access | Bedrock (primary), direct APIs (fallback) | Behind the AI Gateway either way — see the Grounding ADR |
| Secrets | Secrets Manager + KMS | Connector credentials never in env files |
| Identity | IAM + IRSA per agent | Agent identity maps to a real principal |
| Audit | CloudTrail | Independent record of what Pashupatastra actually did |
| Async work | SQS + EventBridge | Ingestion buffering, scheduled verification windows |

## Consequences

**Enables:**
- Managed durability for the audit trail, which is a correctness requirement, not
  a convenience — see [SECURITY.md](../SECURITY.md) T6
- IAM as the enforcement floor beneath Dharma: even a policy bug cannot exceed the
  agent's IAM permissions. Two independent layers, not one.
- CloudTrail as an out-of-band verification source — the benchmark can check what
  the system *actually* did against what it *claims* it did
- AWS-native customers as the first market, with GuardDuty / Security Hub /
  CloudTrail as high-signal Kavach inputs
- Phase 1 spent on the topology graph rather than on operating five datastores

**Rules out:**
- AWS-specific types in `packages/core`, permanently
- Managed-service features without a self-hosted equivalent, where using them
  would break the on-prem path (checked per feature, not assumed)
- Bedrock-only model access — the AI Gateway keeps direct provider APIs viable

**Costs accepted:**
- Cloud spend during the build; benchmark runs are the expensive part
- Two deployment targets to maintain from Phase 3 onward (AWS managed, and a
  docker-compose/self-hosted stack for on-prem and local benchmark runs)

**Revisit when:**
- An enterprise on-prem deal predates the AWS-native GA
- Benchmark cost on managed services becomes the limiting factor on run count

## Alternatives considered

- **Self-host everything on plain EC2 or a home lab** — cheapest, maximum
  portability, but spends the 24 weeks operating Postgres and Elasticsearch
  instead of building the loop.
- **Cloud-agnostic from day one (abstract every service)** — the abstraction cost
  is paid immediately against a benefit that arrives only if a second cloud is
  ever needed. Keeping `core` clean achieves most of the portability for far less.
- **Serverless-first (Lambda + Aurora Serverless + Step Functions)** — attractive
  operationally, but the reasoning loop is long-running and stateful, and the
  Kubernetes connector needs cluster adjacency. EKS matches the problem better.
