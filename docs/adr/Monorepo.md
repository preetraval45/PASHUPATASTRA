# Monorepo until the open-source split

- **Status:** Accepted
- **Date:** 2026-08-10
- **Phase:** Phase 0

## Context

The eventual packaging is a GitHub organization with separate repositories —
`pashupatastra-core`, `-agent`, `-sdk`, `-connectors`, `-benchmark`, `-docs`,
`-ui`, `-examples`. That is the right shape for an open-source ecosystem with
independent consumers and release cadences.

It is the wrong shape today. The interfaces between perception, reasoning,
policy, and action are unknown — they will change materially once real telemetry
lands in Phase 1 and once the policy engine is red-teamed in Phase 3. Splitting
now freezes boundaries chosen before any evidence exists, and every subsequent
cross-cutting change becomes a multi-repo version dance.

## Decision

One monorepo through Phase 5. Internal boundaries are enforced by directory
structure and import discipline (`packages/core` may not import from
`services/api`), not by repository separation. The split happens at Phase 6,
when the open-source release forces the question and the interfaces have been
exercised by a working benchmark.

## Consequences

**Enables:**
- Cross-cutting refactors in a single atomic commit while schemas are unstable
- One CI pipeline, one dependency graph, one version during the build-out
- Boundary decisions made with evidence rather than prediction

**Rules out:**
- Independent versioning or release of `core` before Phase 6
- External consumers depending on `packages/core` prior to the split

**Revisit when:**
- An external party needs to depend on `core` before Phase 6
- Phase 6 begins — the split is then mandatory, not optional

## Alternatives considered

- **Eight repositories now** — matches the eventual open-source shape, but pays
  the coordination cost during exactly the period when interfaces churn most.
- **Two repositories (core + cloud)** — a reasonable middle path, but the OSS/
  commercial line is itself not settled yet, so it splits on an unproven seam.
