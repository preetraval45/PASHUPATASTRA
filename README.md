# PASHUPATASTRA

**Autonomous Intelligence for Complex Systems.**

*Observe. Reason. Act. Verify.*

---

## What this is

Pashupatastra is an AI-native autonomous systems platform. It observes complex
infrastructure, reconstructs its state, reasons about cause and consequence,
predicts what happens next, and safely executes verified remediation — with
humans retaining control over every high-impact decision.

Most platforms stop at `Observe → Alert`. Some AI products reach
`Observe → Explain`. Pashupatastra closes the loop:

```
Observe → Understand → Predict → Decide → Act → Verify → Learn
```

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

**Phase 0 — Foundation.** Repository scaffold, architecture, and roadmap only.
No runtime code yet. See [docs/ROADMAP.md](docs/ROADMAP.md) for the full plan of
action and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system design.

## Research direction

> **Pashupatastra: Policy-Constrained Closed-Loop Autonomous Infrastructure Operations**
>
> Can an AI system safely perform autonomous infrastructure remediation by
> combining observability, causal reasoning, historical incident memory, policy
> constraints, and post-action verification?

Measured against PIB across MTTR, autonomous resolution rate, false remediation
rate, verification success rate, blast radius, and human intervention rate.

## Naming & trademark

The name has an existing commercial web presence. Trademark, corporate-name,
and domain clearance must complete before any public launch commitment. Tracked
in [docs/ROADMAP.md](docs/ROADMAP.md) under Phase 0.

## License

Core is intended for open source; the cloud platform is commercial. License file
to be added once clearance completes.
