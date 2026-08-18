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
| [Schema](Schema.md) — event schema versioning, additive vs. breaking | 2026-08-11 | Accepted |
| [Graph](Graph.md) — topology store: Postgres, p99 18ms vs. a 200ms target | 2026-08-11 | Accepted |
| [Seasonality](Seasonality.md) — seasonal strategy opt-in, and mis-specification reported | 2026-08-17 | Accepted |
| [Smriti](Smriti.md) — hybrid retrieval, and the match basis reported rather than blended | 2026-08-17 | Accepted |

## Planned

| Topic | Phase |
|-------|-------|
| Structural enforcement of the Dharma verdict requirement | 3 |
| Smriti persistence — in-memory vs. a vector store, decided by measurement | 3 |
| PIB harness — fault injection vs. telemetry replay | 5 |
| Open-source / commercial boundary | 6 |

Use [TEMPLATE.md](TEMPLATE.md). Name the file for the decision, in one or two
words.
