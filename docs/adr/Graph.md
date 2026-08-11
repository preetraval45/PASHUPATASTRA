# Topology graph store

- **Status:** Accepted — Postgres (was Deferred; resolved by measurement)
- **Date:** 2026-08-11 (criteria) → 2026-08-11 (decided)
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

## Decision: Postgres

Measured, so no longer a guess. `scripts/benchgraph.py` on a 4,009-node,
10,006-edge graph shaped like a real service topology — six tiers, each node
depending on up to three in the tier below:

| Metric | Result |
|--------|--------|
| Affected nodes per query | median 244, max 770 |
| p50 traversal | 5.7 ms |
| p95 traversal | 12.2 ms |
| **p99 traversal** | **18.3 ms** |
| Roadmap target | < 200 ms |

An order of magnitude inside the budget, on a graph larger than the reference
stack will ever be. Criterion 3 is met decisively, so the default stands.

The recursive CTE lives in `migrations/graph.sql`, and `testgraph.py` asserts it
reproduces `TopologyGraph` in packages/core on every structural case —
transitivity, direction, depth limits, cycles, unknown origins, and the
adjacency gate. That parity matters because blast radius feeds risk scoring: if
the two implementations disagreed, the same action would carry different
authority depending on which code path answered.

**Still open:** criterion 5. Phase 2's query shapes are not yet known, and
path-finding or structural similarity could still justify a dedicated store. The
bar is now higher than it was — a second datastore must beat 18 ms p99 *and*
justify the consistency risk of holding topology apart from the incident record.

## Original decision criteria

Recorded before the measurement, for honesty about what was and was not known:

1. Node and edge counts on the reference stack, and a projection for a realistic
   customer estimate
2. Depth distribution of dependency chains
3. p50/p99 latency of blast-radius traversal in Postgres, against the
   **200ms exit criterion** in the roadmap
4. Reconciliation write volume per minute under normal churn
5. Whether Phase 2's planned queries exceed bounded-depth reachability

**Default was:** Postgres, unless (3) missed the latency target or (5) proved
true. (3) passed by a wide margin; (5) remains unmeasured until Phase 2.

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

**Revisit:** if Phase 2 needs queries beyond bounded-depth reachability, or if
a real customer topology proves an order of magnitude larger than the benchmark.

## Alternatives considered

- **Decide now for Postgres.** Probably the right answer, and it is already the
  working default — but recording it as an accepted decision would overstate the
  evidence behind it.
- **Decide now for a graph database.** Buys capability that nothing currently
  needs, at the cost of a second datastore in the consistency-critical path.
