# ADR: Kaal incident generator — the fault model

- **Status:** Proposed on 26 October 2026 by Claude, at the owner's request
  to start Block B. **Awaiting the owner's decision.** RP-17 makes the fault
  model the owner's design. This document is a starting point to accept,
  change or reject, and the generator follows whatever is decided.
- **Task:** RP-17 (RESEARCH PLAN.md). It feeds RP-18 (dataset v1) and
  RP-24 (Sati-RCA trained on generated incidents).

## Context

Sati-RCA needs thousands of labelled incidents. The 20 hand-labelled ones
are test-only for good. RCAEval gives real ones, but only 3 systems. Kaal's
job is simulation: a generator whose output is cheap, labelled and varied in
the ways that matter (topology, fault, propagation, decoys) and which never
copies the test set.

## Decision (proposed)

### Topology

- **Layers.** A random layered service graph: one or two edge services, two
  to four API services, two to five backends, and one to three datastores
  (database, cache, queue).
- **Calls.** Each service calls one to three services in the layer below.
  Calls only go down, so the graph has no cycles.
- **Names.** Services get neutral names (`svc-07`), never PIB's or RCAEval's,
  so the contamination guard (RP-18) can work by structure, not by name.

### Faults, mapped to PIB's eight categories

| Category | Fault | Where it starts | Metrics at the origin | Correct action | Outcome |
|---|---|---|---|---|---|
| database | connection pool saturation | database | connections ↑, latency ↑ | `scale_service` | remediate |
| cache | eviction storm | cache | hit rate ↓, latency ↑ | `warm_cache` | remediate |
| compute | memory leak | backend | memory ↑, restarts ↑ | `restart_service` | remediate |
| compute | CPU saturation | API or backend | CPU ↑, latency ↑ | `scale_service` | remediate |
| deployment | bad release | API or backend, after a deploy event on it | errors ↑, latency ↑ | `rollback_deployment` | remediate |
| queue | consumer lag | queue | depth ↑, age ↑ | `scale_service` | remediate |
| dependency | third-party outage | edge or API, with an error log naming the dependency | errors ↑ | — | escalate |
| network | packet loss between layers | edge or API | latency ↑, timeouts ↑ | — | escalate |
| security | credential stuffing | edge | auth failures ↑, logins ↑ | — | escalate |

Escalate means the correct answer is to hand off. This matches PIB's view
that third-party outages, network faults and security judgements are human
calls.

### Propagation

A fault moves **up** the call graph, to every service that calls the origin,
directly or through others:

- **Delay:** one to three minutes per hop.
- **Attenuation:** each hop keeps 0.6–0.9 of the deviation.
- **Fading:** propagation stops below 1.5σ.
- **What callers show:** latency and errors only, never the origin's own
  metrics. A caller's slowdown can be larger than the origin's, so the
  loudest service is often not the cause.

### Decoys and negatives

- **Decoys.** About 40% of incidents add one:
  - an unrelated deploy on another service within the window, with no
    effect; or
  - a noisy neighbour: one unrelated service with a short CPU spike.

  Decoys are marked in the label so their effect can be measured, and they
  are never the root.
- **Negatives.** About 20% of incidents have no fault, only noise and maybe a
  decoy. The correct action is to do nothing.

### What an incident is

- **Events.** Drishti `Event`s: a metric event at each anomaly onset with its
  value, baseline and deviation in σ; deployment events; and error logs. Each
  carries provenance `source_system="kaal"` and an `occurred_at` time.
- **Label.** `{root_service, fault_type, category, action, outcome,
  affected (in propagation order), decoys}`.
- **Determinism.** A seed and an index fully determine an incident, using
  `random.Random(f"{seed}:{i}")`.

## Consequences

- **Pure Python in `packages/core`** (`pashupatastra.kaal`). There is no
  torch and no cloud, so it runs anywhere core runs.
- **The model can be gamed.** Faults leave textbook signatures, and a model
  trained only here will learn them. RP-19 (sim-to-real) and RCAEval exist to
  measure that gap, and RP-18's realism report compares generated
  distributions with real ones.
- **Changing this ADR changes the data.** The generator records its version
  in every incident, and RP-18's split manifest pins it.

## What the owner should decide

1. Is the fault catalogue right, and is anything missing from PIB's
   categories?
2. Are the escalate outcomes right? (Security is all-escalate here.)
3. Should decoys be 40% and negatives 20%?
4. Should propagation be upward only, or should some faults (a saturated
   queue blocking producers) also flow down?
