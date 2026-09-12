# PASHUPATASTRA

**Policy-bounded autonomous security operations.**

*Observe. Reason. Act. Verify.*

Live: **[pashupatastra.vercel.app](https://pashupatastra.vercel.app)** ·
Built by **Preet Raval** ([GitHub](https://github.com/preetraval45) ·
[LinkedIn](https://www.linkedin.com/in/preetraval45)) ·
[How it works](https://pashupatastra.vercel.app/how-it-works) ·
[Cite](#cite) · [Research](#research)

---

## What this is

Four alerts in four tools are one intrusion, and most tooling stops after
*detect*. Pashupatastra is a working demonstration of what happens when the
loop is carried through — correlate the telemetry into one incident with a
causal chain, map each step to a MITRE ATT&CK technique, propose remediation,
and let a deterministic policy engine, not the model, decide who has to
authorise it:

```
Observe → Understand → Predict → Decide → Act → Verify → Learn
```

Three properties carry the design, and none of them is a prompt:

- **The model is never the source of truth.** The assistant answers only from
  stored records; every citation is verified against what was actually
  retrieved, and an answer that cites nothing is withheld rather than shown
  with a warning beside it.
- **No action bypasses policy.** Every action is registered with a base risk,
  a declared rollback and an expected post-state; the risk engine scores it
  against the incident's blast radius and confidence, and a tier decides
  whether it runs, waits for an operator, waits for a senior, or never runs.
  The assistant can propose an action; it holds no path to execute one.
- **Everything is a record.** Observations, hypotheses, verdicts, approvals,
  executions, verifications and the assistant's own turns are an append-only
  ledger, on a public page.

**What is real and what is written.** The three incidents are scripted
scenarios, labelled as such on every page — they exist to show the whole
chain, and their confidences are the author's stated numbers, not measured
rates. The threat intelligence in the Observatory is real: CISA KEV, abuse.ch
(URLhaus, Feodo Tracker, ThreatFox), Have I Been Pwned and ransomware.live,
polled hourly, every entry linking to its source. Nothing on the deployed
site executes anything; it is permanently in dry run and says so.

## The problem

A modern stack emits millions of signals across metrics, logs, traces,
deployments, and security events. Monitoring tells you *what happened*. It does
not tell you *why it happened, what happens next, or what the safest recovery
is*. Humans still connect the dots, at 3am, under pressure.

```
09:32  API latency ↑
09:33  DB connections ↑
09:34  Redis memory ↑
09:35  5xx errors ↑
09:36  Transactions ↓
09:37  Page fires
09:40  Human starts guessing
```

Pashupatastra collapses that into a single incident with a causal chain, a
blast-radius estimate, a risk-scored remediation plan, and a verification pass.

## Architecture

```
                    PASHUPATASTRA
                          │
              ┌───────────┴───────────┐
              │                       │
        INTELLIGENCE              CONTROL
              │                       │
       ┌──────┼──────┐          ┌─────┼─────┐
       │      │      │          │     │     │
    Drishti Buddhi Smriti     Astra Kavach Dharma
    observe reason remember    act  defend  govern
       │      │      │          │     │     │
       └──────┴──────┴──────────┴─────┴─────┘
                          │
                     VERIFICATION
                          │
                       LEARNING
```

| Component      | Role                                                        |
| -------------- | ----------------------------------------------------------- |
| **Drishti**    | Perception — normalizes metrics, logs, traces, events        |
| **Smriti**     | Organizational memory — past incidents, fixes, decisions     |
| **Buddhi**     | Reasoning — causal inference, hypotheses, blast radius       |
| **Astra**      | Action — plans, executes, and rolls back remediation         |
| **Kavach**     | Security — detection and correlation of adversarial signals  |
| **Dharma**     | Policy — risk scoring and bounded-autonomy enforcement       |
| **Kaal**       | Simulation — digital twin, "what happens if…"                |

**ASTRA** = *Autonomous System Tactical Response Architecture*.

Pashupatastra does **not** replace Prometheus, Elasticsearch, or OpenTelemetry.
It sits above them as the intelligence and control layer.

## Bounded autonomy

Every action carries a risk score. Policy — not the model — decides who may
execute it.

| Risk    | Example                  | Authority          |
| ------- | ------------------------ | ------------------ |
| 0–30    | read logs, restart, scale| Autonomous         |
| 31–60   | rollback, clear cache    | Approval required  |
| 61–80   | change DB configuration  | Senior approval    |
| 81–100  | delete infrastructure    | Never autonomous   |

The LLM is never the source of truth. It proposes; deterministic policy,
structured tools, and post-action verification dispose.

## Platform

The target platform is AWS: EKS, RDS PostgreSQL, ElastiCache, OpenSearch, S3,
Amazon Managed Prometheus, Bedrock behind the AI Gateway, Secrets Manager, and
CloudTrail as an independent audit mirror. **The public demo runs smaller than
that, on purpose:** Lambda behind an HTTP API, DynamoDB, EventBridge for the
hourly feed poll, Vercel for the site, and a free-tier model provider through
the same gateway — every piece inside a free tier, with the reasoning in
[docs/REBUILD.md](docs/REBUILD.md).

IAM is the floor beneath the policy engine — an agent's IAM role mirrors its
declared permissions, so a policy bug still cannot exceed what the role allows.
Destructive permissions are granted to no Pashupatastra role in any environment.

The core domain model carries no AWS types, so the on-prem/hybrid path stays
open. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and
[the Platform ADR](docs/adr/Platform.md).

## Repository layout

```
apps/web/            Next.js dashboard
services/api/        FastAPI backend (engines, API, models, policies)
packages/core/       Event schema, agent framework, policy engine (OSS)
packages/sdk/        Client SDK
packages/connectors/ Prometheus, OTel, Elasticsearch, Docker, K8s
benchmark/           PIB — Pashupatastra Incident Benchmark
infra/               Docker, Kubernetes, Terraform
docs/                Architecture, ADRs, research
.claude/memory/      Per-push engineering memory log
```

## Status

Delivery is tracked task by task in [docs/REBUILD.md](docs/REBUILD.md) — each
task is ticked only when its evidence exists, and the evidence is written
beside it. In outline, on 12 September 2026:

| What | State |
|---|---|
| Public console: incidents, causal chain, blast radius, action registry, audit trail | Deployed (Phases 1–5B) |
| Sati, the assistant: grounded answers, verified citations, proposals through policy, reasoning trace, cross-incident relations, drafts, detection rules, counterfactuals, argued alternatives | Built; Phase 5C awaiting its live-model measurements |
| Observatory: six real feeds, hourly, grouped by indicator | Deployed |
| Blue Team mode: scored investigation of each scenario, with a debrief | Deployed |
| PIB benchmark and the infrastructure-domain paper draft | Draft — see [Research](#research) |
| The September review pass (Phase 5E) and evidence work (Phase 5F) | In progress |
| Tenancy, sign-in, a product surface (Phases 6–8) | Not started |

The platform roadmap — engines, connectors, benchmark — is
[docs/ROADMAP.md](docs/ROADMAP.md).

## Research

The research question, from the paper draft:

> Can an AI system safely perform autonomous remediation by combining
> observability, causal reasoning, incident memory, policy constraints, and
> post-action verification?

- **Paper draft:** [docs/research/PAPER.md](docs/research/PAPER.md). Its first
  line says it is not submittable and §9 says why — two of four benchmark arms
  have no data, 31 of 104 scenarios execute, diagnosis quality is unmeasured.
- **Benchmark:** [benchmark/](benchmark/) — PIB, 104 authored incident
  scenarios with a fault-injection harness; metrics in
  [docs/research/METRICS.md](docs/research/METRICS.md).
- **Results tables:** [docs/research/tables.md](docs/research/tables.md),
  generated from run records by `scripts/papertables.py` — never transcribed.
- **Evidence plan:** [docs/O1 visa roadmap.md](docs/O1%20visa%20roadmap.md)
  maps what the project can prove to what it cannot yet.

## Run it locally

Python 3.12+ and Node 24. The API runs from memory with the demo scenarios
seeded, in the same configuration the deployed site uses:

```
pip install -e packages/core -e "services/api[dev]"
cd services/api
PASHU_ACTION_DOMAIN=security PASHU_DEMO_SEED=true uvicorn app.main:app --reload
```

```
cd apps/web && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

Tests: `pytest` from the repository root for `packages/core`; from
`services/api`, `pytest` and again with `PASHU_DEMO_SEED=true
PASHU_ACTION_DOMAIN=security` for the seeded suites; `npm test` and `npm run
typecheck` in `apps/web`. The `scripts/verify*.py` checks run against the
deployed site and are named in the task each one proves.

## Cite

From [CITATION.cff](CITATION.cff), which GitHub renders as *Cite this
repository* and `scripts/buildcitation.py` renders for the site:

```bibtex
@software{raval2026pashupatastra,
  author = {Raval, Preet},
  title = {Pashupatastra: policy-bounded autonomous security operations},
  year = {2026},
  month = {9},
  version = {0.1.0},
  url = {https://pashupatastra.vercel.app},
}
```

No DOI yet — one is minted from a tagged release once the repository carries a
licence.

## Naming & trademark

The name has an existing commercial web presence. Trademark, corporate-name,
and domain clearance must complete before any public launch commitment. Tracked
in [docs/ROADMAP.md](docs/ROADMAP.md) under Phase 0.

## License

Not yet decided, and stated rather than implied: the core is intended for open
source and the cloud platform is commercial, and the file arrives when that
decision does. Until then the repository is public source without a licence,
which means all rights reserved — read it, cite it, and ask before reusing it.
