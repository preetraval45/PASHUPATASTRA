# Security & Threat Model

**Status:** Phase 0 draft. Reviewed before any live-execution capability ships.

Pashupatastra holds credentials to production infrastructure and can change its
state. It is, by construction, a high-value target and a potential single point
of catastrophic failure. The threat model is therefore part of the architecture,
not an afterthought.

## Trust boundaries

```
Untrusted ──────────────────────────────────► Trusted
  telemetry   model output   operator input   policy engine
  (attacker-  (hallucination (authenticated   (deterministic,
   influenced) risk)          + authorized)    audited)
```

**Telemetry is untrusted input.** An attacker who can write to logs can inject
text the reasoner reads. Log content is data, never instruction.

**Model output is untrusted.** It proposes; it never authorizes. A verdict comes
from Dharma, which is deterministic code, not a model call.

## Primary threats

| # | Threat | Control |
|---|--------|---------|
| T1 | Prompt injection via logs/metrics into Buddhi | Telemetry is quoted data, never instruction; actions come only from the registry, never from parsed model text |
| T2 | Compromised Pashupatastra → attacker controls infrastructure | Least-privilege connector credentials; per-environment scoping; destructive actions never autonomous; short-lived verdicts |
| T3 | Model-induced wrong remediation | Evidence-required hypotheses; risk tiers; expected-state verification; automatic rollback |
| T4 | Attacker triggers a fake incident to induce a harmful "fix" | Correlation requires topology adjacency; novelty penalty raises risk; blast-radius escalation |
| T5 | Credential exfiltration through the AI Gateway | Secrets never enter prompts; redaction at ingestion; gateway-level egress policy |
| T6 | Audit tampering to hide an action | Append-only audit store; verdicts recorded before execution, not after |
| T7 | Runaway agent loop consuming resources or acting repeatedly | Hard per-incident budgets — tokens, actions, wall clock; exhaustion escalates |
| T8 | Privilege creep via agent redefinition | Agent declarations are versioned, reviewed, and environment-promoted explicitly |
| T9 | Leaked AWS credentials grant an attacker the platform's own infrastructure authority | No long-lived keys; SSO + MFA for humans, IRSA for workloads, OIDC for CI; per-environment account separation; destructive permissions granted to no role |

## AWS credential handling

The platform is AWS ([the Platform ADR](adr/Platform.md)), which makes
credential hygiene a first-order concern rather than a checklist item.

- **No long-lived IAM user access keys.** Humans use IAM Identity Center (SSO)
  with MFA; workloads use IRSA; CI uses GitHub OIDC federation. Nothing static.
- **Root account is locked down** — MFA, no access keys, used for nothing routine.
- **Credentials never appear in chat, prompts, issues, commits, or logs.** Any
  credential that is pasted anywhere is treated as compromised and rotated
  immediately, regardless of who saw it.
- **Secrets Manager + KMS** for all connector credentials; none in env files,
  images, or Terraform state.
- **Account separation** dev / staging / prod. Production execution credentials
  are unreachable from lower environments.
- `.gitignore` blocks `.env`, `*.pem`, `*.key`, `credentials.json`, and
  `*.tfstate` — but the control is the practice, not the ignore file.

## Non-negotiable controls

1. Dry-run is the default. Live execution is opt-in per environment.
2. No shell, no raw cloud credentials, in any model-reachable tool. Actions are
   a closed registry of typed, parameterized operations.
3. Secrets are redacted at ingestion, before storage and before any prompt.
4. Every action has a tested rollback, or it is not autonomous.
5. Audit records are append-only and written pre-execution.
6. Destructive/irreversible operations are permanently outside autonomy.

## Kavach — the defensive-detection side

Kavach is detection and correlation only. It does not perform offensive actions,
active response against third parties, or anything outside the customer's own
declared assets. Its remediation authority runs through Dharma exactly like any
other action — isolation and quarantine are high-risk tiers requiring approval.

## Data handling

Customer telemetry may contain personal data. Retention is configurable per
class; PII redaction runs at ingestion; on-prem deployment exists specifically
so regulated customers can keep telemetry inside their boundary.

## Reporting

Vulnerability disclosure process to be published with the open-source release
(Phase 6). Until then, report privately to the maintainer.
