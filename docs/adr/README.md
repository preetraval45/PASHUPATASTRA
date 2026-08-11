# Architecture Decision Records

Decisions that constrain future work. Immutable — supersede rather than edit.
Files are named for their topic; order is recorded here by date, not by a number
in the filename.

| Decision | Date | Status |
|----------|------|--------|
| [Monorepo](Monorepo.md) — one repo until the open-source split | 2026-08-10 | Accepted |
| [Grounding](Grounding.md) — the LLM is not the source of truth | 2026-08-10 | Accepted |
| [Observability](Observability.md) — sit above existing tooling, never replace it | 2026-08-10 | Accepted |
| [Platform](Platform.md) — AWS as the target, `packages/core` cloud-free | 2026-08-10 | Accepted |

## Planned

| Topic | Phase |
|-------|-------|
| Event schema v0 boundaries and versioning | 0 |
| Knowledge graph store — Postgres CTEs vs. graph DB | 1 |
| Smriti retrieval — embeddings vs. hybrid | 2 |
| Structural enforcement of the Dharma verdict requirement | 3 |
| PIB harness — fault injection vs. telemetry replay | 5 |
| Open-source / commercial boundary | 6 |

Use [TEMPLATE.md](TEMPLATE.md). Name the file for the decision, in one or two
words.
