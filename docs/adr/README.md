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
| [SatiModels](SatiModels.md) — Sati stays the agent; Sati-Detect/-RCA/-Embed/-LM are the models it runs on, trained here | 2026-10-18 | Accepted |
| [ExternalBenchmark](ExternalBenchmark.md) — feasibility of RCAEval, OpenRCA, AIOpsLab, ITBench; RCAEval chosen | 2026-10-18 | Accepted |
| [RealDataModels](RealDataModels.md) — Claude builds and trains every Sati model on real public data, on free cloud compute; splits that test diagnosis, not memory | 2026-10-18 | Accepted |
| [Navadurga](Navadurga.md) — the nine Sati models, named for Navadurga, each with the job that fits its form; Katyayani (root cause) trained first | 2026-10-18 | Accepted |
| [LLMBaselines](LLMBaselines.md) — 2 × 2: {deterministic, LLM} proposer × {no policy, Dharma + verification}; LLMs are baselines only | 2026-10-18 | Accepted |
| [SatiDetect](SatiDetect.md) — Shailaputri v0 beats every statistical detector on F1 but not on lead time; statistical default stays, model is a second opinion | 2026-10-18 | Accepted |

## Planned

| Topic | Phase |
|-------|-------|
| Structural enforcement of the Dharma verdict requirement | 3 |
| Smriti persistence — in-memory vs. a vector store, decided by measurement | 3 |
| PIB harness — fault injection vs. telemetry replay | 5 |
| Open-source / commercial boundary | 6 |

Use [TEMPLATE.md](TEMPLATE.md). Name the file for the decision, in one or two
words.
