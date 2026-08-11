# Specification — Normalized Event Model (v0)

**Status:** Draft. Not yet implemented. Implementation lands in `packages/core/`
during Phase 0.4 and is first exercised in Phase 1.

## Purpose

Every connector — Prometheus, OpenTelemetry, Elasticsearch, Docker, Kubernetes,
CI/CD, security tooling — emits into one shape. Every downstream engine reads
only this shape. Connectors are therefore replaceable and the reasoning layer
never learns a vendor's quirks.

## Design rules

1. **Provenance is mandatory.** Every event names its source and carries a
   reference that lets a human re-query the original system.
2. **Entities are references, not strings.** An event points at a topology node
   ID, so the graph and the telemetry share one namespace.
3. **Time is explicit and dual.** `occurred_at` (when it happened in the source)
   and `observed_at` (when Pashupatastra saw it) are separate; the gap matters
   for causal ordering.
4. **Payloads are typed by class**, not free-form JSON blobs the reasoner must
   guess at.

## Shape

```
Event
├── id                  ULID, sortable by observation time
├── class               metric | log | trace | state_change | deployment
│                       | security | alert | human_action
├── source              connector identity + version
├── occurred_at         source-side timestamp (UTC)
├── observed_at         ingestion timestamp (UTC)
├── entity_ref          topology node ID (service, host, container, db, …)
├── severity            info | warning | critical  (nullable)
├── payload             class-specific typed body
├── provenance          query/URL/offset to retrieve the original record
└── labels              normalized key/value dimensions
```

## Class payloads

| Class | Payload carries |
|-------|-----------------|
| `metric` | name, value, unit, aggregation window, baseline, deviation |
| `log` | message, level, structured fields, trace correlation |
| `trace` | trace/span IDs, duration, status, parent, service hops |
| `state_change` | resource, previous state, new state, actor |
| `deployment` | service, version, previous version, actor, commit, strategy |
| `security` | detection type, principal, source address, asset, confidence |
| `alert` | upstream rule ID, condition, upstream severity, upstream state |
| `human_action` | operator, action taken, incident ref, rationale |

`deployment` matters disproportionately — change correlation is the single
highest-yield causal signal, so it gets a first-class class rather than being
buried in `state_change`.

## Entity references

```
entity_ref = { kind, id, cluster?, namespace?, name }
kind ∈ service | host | container | pod | database | cache | queue
    | loadbalancer | endpoint | user | deployment | cloud_resource
```

Resolution is the connector's job. An event whose entity cannot be resolved into
the topology graph is quarantined, not silently dropped — unresolvable entities
are a symptom of stale topology and must be visible.

## Versioning

The schema is versioned from v0. Breaking changes bump the version, ship a
migration, and require an ADR. Phase 1 is the first real migration test — the
schema is expected to be wrong in ways only live telemetry reveals.

## Open questions

- Do metric events stream at full resolution or only on anomaly? Full resolution
  is simpler to reason over and far more expensive. Decide in Phase 1.
- Retention split between Postgres, Elasticsearch, and object storage.
