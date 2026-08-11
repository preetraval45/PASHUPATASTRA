# Terraform — AWS

**Status:** skeleton. Providers and variables only; resources land per phase.

| Phase | Lands here |
|-------|------------|
| 0.5 | Account structure, VPC, RDS PostgreSQL (Multi-AZ in prod), ElastiCache, OpenSearch, S3, CloudTrail, budget alarms |
| 1 | Amazon Managed Prometheus + Grafana workspaces, read-only connector IAM |
| 3 | EKS, IRSA roles per agent, execution IAM (write, still no destructive permissions) |
| 5 | Ephemeral benchmark environment — provisioned per run, torn down after |

## Rules

- **No long-lived IAM user access keys.** Humans use Identity Center with MFA,
  workloads use IRSA, CI uses GitHub OIDC. Nothing static, anywhere.
- **Destructive permissions are granted to no Pashupatastra role**, in any
  environment. `delete_infrastructure` is permanently outside autonomy
  (docs/specs/Policy%20Model.md), so granting it would add risk without capability.
- **Read and write roles are separate**, so perception credentials cannot mutate
  anything and Drishti is structurally incapable of causing an incident.
- State lives in S3 with a DynamoDB lock table, configured per environment via
  `-backend-config`. `*.tfstate` is gitignored — state contains resource metadata
  and sometimes secrets.

## Usage

```sh
terraform init -backend-config=envs/dev.backend.hcl
terraform plan  -var-file=envs/dev.tfvars
```
