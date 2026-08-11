# Topology graph store

- **Status:** Deferred — decision due in Phase 1
- **Date:** 2026-08-11
- **Phase:** Phase 0 (criteria) → Phase 1 (decision)

## Context

The topology graph answers two questions that everything else depends on: what
breaks when this breaks (blast radius), and are these two failures related
(the adjacency gate for correlation). Both are reachability queries over a
directed graph of a few thousand nodes.

The obvious candidates — Postgres with recursive CTEs, or a dedicated graph
store such as Neptune — differ on axes that cannot be measured yet, because no
real topology exists. Choosing now would be choosing on aesthetics.

## Why this is deferred rather than decided

The honest inputs are all missing:

- **Graph size and shape.** A few hundred nodes with shallow dependency chains
  is trivially a Postgres problem. Tens of thousands with deep chains is not.
- **Query mix.** Blast radius is a bounded-depth walk from one node. If that is
  99% of the load, recursive CTEs with a `target_key` index are likely enough.
  If Phase 2 wants path-finding, subgraph matching, or similarity over
  structure, that calculus changes.
- **Write pattern.** Continuous reconciliation against live infrastructure means
  the graph churns. Write amplification matters more than read elegance.
- **Temporal queries.** "What did the topology look like when this incident
  opened?" is a Smriti requirement that neither option handles for free, and it
  may dominate the decision.

Deciding before Phase 1 measures these would encode a guess as an ADR, which is
worse than no ADR — it would carry the authority of a decision without the
evidence of one.

## Decision criteria

Phase 1 must produce these numbers before this ADR is written:

1. Node and edge counts on the reference stack, and a projection for a realistic
   customer estimate
2. Depth distribution of dependency chains
3. p50/p99 latency of blast-radius traversal in Postgres, against the
   **200ms exit criterion** in the roadmap
4. Reconciliation write volume per minute under normal churn
5. Whether Phase 2's planned queries exceed bounded-depth reachability

**Default:** Postgres, unless (3) misses the latency target or (5) is true. The
schema already carries `topology_node` and `topology_edge` with a `target_key`
index, so the default is testable on day one of Phase 1 at no cost.

The bar for adding a second datastore is high. It is another thing to run,
back up, secure, and keep consistent with Postgres — and inconsistency between
the graph and the incident record would be a correctness bug in blast radius,
which is an input to risk scoring. That coupling is why elegance alone does not
justify the split.

## Consequences of deferring

**Enables:**

- A decision made on measurements rather than instinct
- Phase 1 starting immediately against the Postgres default, at no lost work if
  it is later replaced — `TopologyGraph` in core defines the semantics any store
  must reproduce, and the in-memory implementation is the reference

**Risks:**

- Postgres-shaped assumptions leaking into calling code, making a later swap
  expensive. Mitigation: all traversal goes through the `TopologyGraph`
  interface; no caller writes SQL against `topology_edge` directly.

**Revisit:** when Phase 1's exit criterion is measured. This ADR is then either
superseded by **Graph store: Postgres** or **Graph store: dedicated**.

## Alternatives considered

- **Decide now for Postgres.** Probably the right answer, and it is already the
  working default — but recording it as an accepted decision would overstate the
  evidence behind it.
- **Decide now for a graph database.** Buys capability that nothing currently
  needs, at the cost of a second datastore in the consistency-critical path.
