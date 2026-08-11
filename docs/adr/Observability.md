# Sit above existing observability, never replace it

- **Status:** Accepted
- **Date:** 2026-08-10
- **Phase:** Phase 0

## Context

There is a tempting version of this product that owns the full stack: its own
agent, its own collection pipeline, its own time-series store, its own log
index. It gives complete control over data quality and removes dependency on
other vendors.

It also means competing with Prometheus, Elasticsearch, Datadog, and Grafana on
their own ground — years of engineering that has nothing to do with the actual
thesis — while asking customers to rip out working infrastructure before they
have seen any value.

## Decision

Pashupatastra is an intelligence and control layer above existing observability.
It consumes Prometheus, OpenTelemetry, Elasticsearch, cloud APIs, and CI/CD
systems through connectors. It does not implement collection agents, a
time-series database, or a log index.

```
              PASHUPATASTRA          ← reasoning, policy, action, verification
                    ▲
   Prometheus · Elasticsearch · OpenTelemetry   ← collection and storage
```

## Consequences

**Enables:**
- Value on day one against a customer's existing stack — no migration required
- Engineering effort concentrated on the differentiator
- A far shorter path to the Phase 1 exit criterion

**Rules out:**
- Owning data quality end-to-end — garbage in remains a real failure mode
- Serving customers with no observability at all; they are not the first market
- Storage-layer margin

**Revisit when:**
- Connector-side data gaps become the dominant cause of benchmark failures

## Alternatives considered

- **Full-stack observability platform** — larger surface, larger TAM, but
  competes with mature incumbents on undifferentiated work and delays the
  actual thesis by years.
- **Prometheus-only** — simpler, but the causal reasoning depends on correlating
  metrics with logs, traces, and deployments. One signal type is not enough to
  build a causal chain.
