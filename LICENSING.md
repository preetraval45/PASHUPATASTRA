# Licensing

This repository is **open core**. Different parts carry different terms, and
each licensed directory has its own `LICENSE` file.

| Path | Terms |
|---|---|
| `packages/core/` | [Apache-2.0](packages/core/LICENSE) |
| `packages/sati/` (code, and trained Sati model weights when released) | [Apache-2.0](packages/sati/LICENSE) |
| `packages/sdk/` | [Apache-2.0](packages/sdk/LICENSE) |
| `benchmark/` (harness and PIB scenarios) | [Apache-2.0](benchmark/LICENSE) |
| Everything else: `services/`, `apps/`, `infra/`, `packages/connectors/`, `scripts/`, `docs/` | **All rights reserved** for now. Read it, cite it, and ask before reusing it. Decided at the open-source split (plan Backlog 6.2). |
| The logo artwork | **Not licensed.** Its provenance is not established ([BRAND.md](docs/BRAND.md)), so no licence here covers it. |

Copyright 2026 Preet Raval.

Decided by the owner on 18 October 2026 ([SatiModels ADR](docs/adr/SatiModels.md)).
Anything published under Apache-2.0 stays available under it; the reserved
parts can be opened later, but the open parts cannot be closed again.

Third-party data used for evaluation keeps its own licence. RCAEval, for
example, is MIT on Hugging Face and CC-BY-4.0 on Zenodo
([ExternalBenchmark ADR](docs/adr/ExternalBenchmark.md)).
