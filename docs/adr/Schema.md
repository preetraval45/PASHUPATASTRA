# Event schema versioning

- **Status:** Accepted
- **Date:** 2026-08-11
- **Phase:** Phase 0

## Context

The normalized event model is the widest interface in the system. Every
connector writes it, every engine reads it, Smriti stores it for years, and the
benchmark replays it. It is also the schema most likely to be wrong right now:
it was designed before a single byte of real telemetry arrived, and Phase 1 is
the first thing that will tell us how.

Two failure modes are in tension. Freeze the schema too hard and connectors
start smuggling real structure into `labels` as stringly-typed junk, which moves
the mess somewhere the validator cannot see it. Let it drift freely and stored
incidents from six months ago stop being readable — which destroys Smriti, whose
entire value is that old incidents remain comparable to new ones.

## Decision

The schema carries an explicit `schema_version`, starting at `v0`, and changes
are classified before they are made.

**Additive (no version bump).** Ship freely.

- A new optional field with a default
- A new event class or payload type
- A new `EntityKind`, `Severity`, or label key
- Widening a constraint — a stricter bound becoming looser

**Breaking (version bump + migration + ADR).**

- Removing or renaming any field
- Making an optional field required
- Changing a field's type or its units
- Narrowing a constraint, including tightening an enum
- Changing the meaning of an existing field while keeping its name — **the most
  dangerous category, because nothing mechanical detects it**

The last one is why classification is a written step rather than a diff review.
A field that silently changes meaning passes every test and corrupts years of
stored incidents.

**Rules that follow:**

1. **Readers accept the current version and one prior.** Two versions live
   simultaneously; a third means a migration was skipped.
2. **Stored events are never rewritten in place.** Migration is a read-time
   upcast, so history stays as it was recorded. An append-only audit trail that
   gets retro-edited is not an audit trail.
3. **`labels` is for dimensions, not for structure.** A connector needing a
   typed field asks for a schema change. Overflow into `labels` is the failure
   this rule exists to prevent, and it is a review-bar item.
4. **`v0` is explicitly unstable.** Until the Phase 1 exit criterion is met,
   breaking changes need only the migration, not the ADR. `v1` is declared when
   real telemetry has flowed and the shape has stopped moving; after that, the
   full process applies.
5. **Every breaking change ships with a round-trip test** proving a prior-version
   event still reads correctly.

## Consequences

**Enables:**

- Smriti retrieval across years without a re-indexing project
- Connectors and engines versioning independently
- Benchmark fixtures that stay valid as the platform evolves
- A clear answer to "can I add this field?" that does not need a meeting

**Rules out:**

- Silent semantic changes to existing fields
- More than two live schema versions at once
- Structure hidden in `labels` to dodge the process
- Rewriting stored history to match a new shape

**Revisit when:**

- Phase 1 completes and `v1` is declared — the `v0` grace period ends there
- Three live versions become genuinely unavoidable, which would mean this policy
  failed rather than that it needs relaxing

## Alternatives considered

- **No versioning; keep the schema backward-compatible forever.** Cheapest until
  the first genuine mistake, then permanent. Given the schema was written before
  any real telemetry, assuming no mistakes is not credible.
- **Version every event class separately.** More precise, and it lets one
  connector evolve alone. Rejected because cross-class reasoning — correlating a
  deployment with a metric — would then need a compatibility matrix rather than
  a single version check.
- **Schema registry with runtime negotiation** (Avro/Protobuf style). The right
  answer at high connector count and real operational cost now. Revisit if
  third-party connectors arrive after the open-source split.
