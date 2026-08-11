# Specification — Incident Model (v0)

**Status:** Draft. Not yet implemented. Lands across Phases 2–4.

## Purpose

An incident is the unit of work. It replaces the alert storm: many events, one
incident, one causal chain, one plan, one verification record, one audit trail.

## Lifecycle

```
detected → correlated → diagnosed → planned → awaiting_approval
   → executing → verifying → resolved
                          ↘ verification_failed → rolled_back
                          ↘ escalated (human takes over)
```

Every transition is an append-only audit record naming the actor — agent or
human — and its justification. Incidents are never edited in place; state is the
fold of its transitions.

## Structure

```
Incident
├── id                   INC-YYYY-NNNN
├── state                lifecycle state above
├── severity             critical | high | medium | low
├── opened_at / closed_at
├── affected_entities[]  topology node refs
├── impact
│   ├── estimated_users_affected
│   ├── affected_services[]
│   └── blast_radius     graph-computed
├── events[]             the correlated evidence
├── hypotheses[]         ranked causal explanations
├── causal_chain         the accepted explanation
├── plan                 ordered remediation steps
├── approvals[]          who authorized what, when
├── executions[]         what actually ran, with results
├── verification         expected vs. observed post-state
└── similar_incidents[]  Smriti retrieval results
```

## Correlation

Events group into one incident when they are adjacent in the topology graph and
adjacent in time. Topology adjacency is what prevents the naive failure mode:
two unrelated services degrading in the same minute are two incidents, not one.

## Hypotheses

```
Hypothesis
├── statement          natural language, generated
├── confidence         0.0–1.0
├── evidence[]         event IDs supporting it — REQUIRED, non-empty
├── contradicted_by[]  events that argue against it
└── mechanism          the causal chain it implies
```

**A hypothesis with no evidence is suppressed, not surfaced at low confidence.**
This is the rule that keeps the reasoner honest. `contradicted_by` exists so the
system can show its own doubt rather than presenting one confident story.

## Causal chain

An ordered directed chain of entity-level state transitions:

```
deployment v4.21
   → query volume ↑ (api)
   → connection pool saturation (postgres)
   → request queue growth (api)
   → request timeout (fastapi)
   → 5xx rate ↑ (nginx)
   → transaction failure (checkout)
```

Each link cites the events that evidence it. A chain rendered to an operator
without citations is a story, not a diagnosis.

## Plan and verification

Each plan step names its action, risk score, expected post-state, and rollback.
Verification observes actual post-state over a defined window and compares:

```
Action              Expected              Observed        Result
rollback v4.21      version = v4.20       v4.20           ✓
db connections      < 70%                 41%             ✓
api latency         < 400ms               180ms           ✓
5xx rate            < 1%                  0.2%            ✓
transaction success > 99%                 99.7%           ✓
```

Any ✗ triggers rollback and escalation. The outcome — success or failure — is
written to Smriti. Failures are more valuable training signal than successes and
are retained with equal prominence.
