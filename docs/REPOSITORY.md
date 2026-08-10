# Repository Structure

Every directory below exists today. Those marked **empty** hold only a
`.gitkeep` — they are the agreed shape, populated in the phase noted.

```
PASHUPATASTRA/
├── README.md                     Thesis, architecture, status
├── CLAUDE.md                     Engineering rules for Claude Code
├── .gitignore
│
├── .claude/memory/               Per-push engineering memory
│   ├── INDEX.md                  One line per push
│   ├── TEMPLATE.md
│   └── NNNN-*.md                 Entries
│
├── docs/
│   ├── README.md                 Documentation index — start here
│   ├── ARCHITECTURE.md           Subsystems, data flow, non-goals
│   ├── ROADMAP.md                24-week plan of action
│   ├── REPOSITORY.md             This file
│   ├── GLOSSARY.md               Every term, defined once
│   ├── SECURITY.md               Threat model, trust boundaries
│   ├── CONTRIBUTING.md           Workflow, commits, review bar
│   ├── adr/                      Architecture decision records
│   ├── specs/                    Event, incident, policy, agent models
│   └── research/                 Paper outline, metric definitions
│
├── apps/web/                     [empty · Phase 1] Next.js dashboard
│
├── services/api/app/             [empty · Phase 0.6+] FastAPI backend
│   ├── engines/                  Incident, agent, reasoning, action, audit
│   ├── api/                      Route handlers
│   ├── models/                   Pydantic + ORM models
│   └── policies/                 Dharma policy definitions
│
├── packages/
│   ├── core/                     [empty · Phase 0.4] Event schema, agent
│   │                             framework, policy engine, incident model
│   ├── sdk/                      [empty · Phase 6] Client SDK
│   └── connectors/               [empty · Phase 1] Prometheus, OTel,
│                                 Elasticsearch, Docker, Kubernetes
│
├── benchmark/                    PIB — Pashupatastra Incident Benchmark
│   ├── README.md                 Scenario format, categories, arms
│   ├── incidents/                [empty · Phase 5] Scenario YAML
│   └── results/                  [empty · Phase 5] Run output (gitignored)
│
├── infra/
│   ├── docker/                   [empty · Phase 1] Reference stack
│   ├── k8s/                      [empty · Phase 1] Manifests
│   └── terraform/                [empty · Phase 3] Provisioning
│
├── scripts/                      [empty] Developer tooling
└── .github/workflows/            [empty · Phase 0] CI
```

## Import discipline

The monorepo has no repository boundaries yet ([ADR 0001](adr/0001-monorepo-until-oss-split.md)),
so direction is enforced by discipline and CI:

```
apps/web  ──►  services/api  ──►  packages/core
                     │                  ▲
                     └──► packages/connectors ──┘
```

- `packages/core` imports nothing from `services/` or `apps/`. It is the future
  open-source package and must stay independently extractable.
- `packages/connectors` depends on `core` for the event model, nothing else.
- Violating this direction now means an expensive untangle at the Phase 6 split.

## Where things go

| Adding… | Goes in |
|---------|---------|
| A new telemetry source | `packages/connectors/` |
| A new executable action | `services/api/app/engines/` + registry entry with risk score, expected post-state, rollback |
| A new policy rule | `services/api/app/policies/` |
| A schema shared across layers | `packages/core/` |
| A benchmark scenario | `benchmark/incidents/` |
| A decision constraining future work | `docs/adr/` |
| Context the next session needs | `.claude/memory/` |
