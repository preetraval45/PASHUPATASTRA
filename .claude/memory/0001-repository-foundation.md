# 0001 — Repository foundation

- **Date:** 2026-08-10
- **Phase:** Phase 0 — Foundation
- **Commit(s):** `64356ff`

## What changed

The repository went from empty to a full Phase 0 scaffold: `README.md` stating
the thesis and architecture, `CLAUDE.md` carrying the engineering rules,
`docs/ARCHITECTURE.md` with the subsystem design and data model,
`docs/ROADMAP.md` with the 24-week plan of action, the `.claude/memory/`
protocol, and placeholder trees for `apps/`, `services/`, `packages/`,
`benchmark/`, and `infra/`. No runtime code exists yet — deliberately.

## Why

The project's differentiator is safety and rigor, not speed to first script. If
the policy engine and audit trail are retrofitted onto working automation, they
become optional in practice. Writing the constraints down before the first
engine exists makes them structural. The docs also double as the skeleton of the
research paper, so the architecture and the publishable contribution stay in
sync from day one.

## Decisions made

- **Monorepo, not eight repositories yet.** The GitHub-org split
  (`pashupatastra-core`, `-agent`, `-sdk`, …) is the eventual open-source
  packaging, but splitting before the interfaces stabilize would freeze the
  wrong boundaries. Split at Phase 6, when the OSS release forces it.
- **Sanskrit subsystem names are load-bearing in code**, not just marketing —
  module prefixes are `drishti`, `smriti`, `buddhi`, `astra`, `kavach`,
  `dharma`, `kaal`. Rules out renaming these casually later.
- **Dharma (policy) is a hard dependency of Astra (action), enforced at the type
  level.** There will be no execution path that does not carry a policy verdict.
- **AI Gateway abstraction from the start.** Rules out direct model-SDK imports
  inside engine code and keeps vendor swap cheap.
- **Sits above Prometheus/OTel/Elasticsearch, never replaces them.** Rules out
  building ingestion pipelines or a TSDB.
- **Name clearance is a Phase 0 blocker.** The name has an existing commercial
  web presence; no public launch, incorporation, or domain-portfolio spend until
  USPTO, state corporate-name, and handle checks complete.

## Open questions

- Legal name clearance outcome — may force `Pashupatastra Labs/Systems/AI` or a
  different public brand. Internal codename can survive either way.
- Knowledge graph store: Postgres with recursive CTEs vs. a dedicated graph DB.
  Deferred until the topology model's real query shapes are known (Phase 1).
- Whether Smriti retrieval is embeddings-only or hybrid with structured incident
  attributes. Likely hybrid; decide in Phase 2.
- PIB incident harness: containerized fault injection vs. simulated telemetry
  replay. Replay is cheaper; injection is more credible for the paper.

## Next session should

Write ADR 0001 (monorepo boundaries) and ADR 0002 (event schema), then define
the normalized event model in `packages/core/` — it is the dependency of every
other component and should exist before any connector code.
