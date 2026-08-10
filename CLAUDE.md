# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

Pashupatastra — an AI-native autonomous systems platform. It closes the loop
`Observe → Understand → Predict → Decide → Act → Verify → Learn` over
infrastructure, with policy-bounded autonomy. See [README.md](README.md) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Current state

Phase 0 — Foundation. Scaffold, docs, and roadmap only. Directories under
`apps/`, `services/`, and `packages/` are placeholders with `.gitkeep`.

## Naming conventions (non-negotiable)

Subsystems use the Sanskrit names, consistently, in code and docs:

| Name      | Subsystem              | Package/module prefix |
| --------- | ---------------------- | --------------------- |
| Drishti   | Perception             | `drishti`             |
| Smriti    | Memory                 | `smriti`              |
| Buddhi    | Reasoning              | `buddhi`              |
| Astra     | Action engine          | `astra`               |
| Kavach    | Security               | `kavach`              |
| Dharma    | Policy engine          | `dharma`              |
| Kaal      | Simulation / twin      | `kaal`                |

Brand tone is "ancient concept → modern intelligence". Do **not** add religious
or fantasy imagery, illustrated deities, or mythological flourish to UI copy,
docs, or assets. The mythology stays subtle — names only.

## Engineering rules

1. **The LLM is never the source of truth.** Reasoning output must be grounded
   in retrieved telemetry, the knowledge graph, or deterministic rules. Any
   claim an engine surfaces carries a provenance reference.
2. **No action bypasses Dharma.** Every executable action is registered with a
   risk score and routed through policy evaluation. There is no "just run it"
   path, not even in dev fixtures.
3. **Every action defines its rollback and its expected post-state** before
   execution. Verification compares observed state to expected state.
4. **Structured outputs everywhere.** Model calls return validated Pydantic
   schemas, never free text that later gets parsed.
5. **Vendor-neutral AI.** All model access goes through the AI Gateway
   abstraction. No direct SDK calls from engine code.
6. **Audit everything.** Observations, hypotheses, decisions, approvals,
   executions, and verifications are append-only records.

## Stack

- Frontend: Next.js, TypeScript, Tailwind, React
- Backend: FastAPI, Python, Pydantic, async workers
- Data: PostgreSQL, Redis, Elasticsearch, object storage
- Observability: OpenTelemetry, Prometheus, Grafana, Elasticsearch
- Infra: Docker, Kubernetes, Terraform, GitHub Actions

## Memory protocol — required on every push

Before each push, append a memory entry under `.claude/memory/`:

- One file per push: `.claude/memory/NNNN-<kebab-slug>.md`
- Use the template at `.claude/memory/TEMPLATE.md`
- Add a one-line pointer to `.claude/memory/INDEX.md`

Record *why*, decisions made, and what the next session needs to know — not a
restatement of the diff, which git already holds.

## Conventions

- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`)
- Branches: `main` is the default and PR target
- ADRs: `docs/adr/NNNN-title.md` for any decision that constrains future work
