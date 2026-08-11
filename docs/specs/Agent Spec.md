# Specification — Agent Model (v0)

**Status:** Draft. Not yet implemented. Lands in Phase 3.

## Purpose

An agent is a scoped, auditable actor — not a model with shell access. Every
agent carries identity, permissions, tools, memory, policies, goals, budget, and
risk limits. Anything it can do, it can do because a declaration says so.

## Declaration

```yaml
agent:
  name: database-responder
  role: Diagnose and remediate database-layer incidents
  version: 1

identity:
  principal: agent:database-responder
  environments: [staging]        # prod requires explicit promotion

permissions:
  read_metrics: true
  read_logs: true
  restart_service: true
  modify_database: false

tools:
  - prometheus.query
  - elasticsearch.search
  - topology.blast_radius
  - smriti.retrieve
  - astra.restart_service

memory:
  smriti_scope: [database, cache]
  retention: 90d

risk_limit: 40
approval:
  required_above: 40

budget:
  tokens_per_incident: 200000
  actions_per_incident: 5
  wall_clock: 10m

goals:
  - Restore database availability
  - Minimize blast radius
  - Escalate rather than guess
```

## Guarantees

1. **Least privilege by declaration.** A tool absent from `tools` is unreachable,
   not merely discouraged.
2. **`risk_limit` is a ceiling, not a preference.** An agent with limit 40 cannot
   execute a risk-45 action even with human approval — approval routes to an
   agent or human authorized for that tier.
3. **Budgets are enforced, not advisory.** Exhausting tokens, actions, or wall
   clock escalates to a human. Runaway loops terminate rather than spend.
4. **Environment promotion is explicit.** An agent proven in staging does not
   automatically gain production authority.
5. **Every tool call is audited** with arguments, result, and the incident it
   served.

## MVP topology

```
        Orchestrator
             │
   ┌─────────┼─────────┐
   │         │         │
Incident  Infra    Security
 Agent    Agent     Agent
```

The full fleet — Commander → SRE / Security / DB / DevOps / Network / Cloud —
comes later, and only once the policy layer has survived a red-team pass. More
agents multiply the surface area of every safety gap.

## Escalation

An agent escalates when: confidence is below threshold, required risk exceeds
its limit, budget is exhausted, verification fails, or the situation is
unrecognized by Smriti. **Escalating is a success outcome, not a failure** — the
benchmark measures false remediation rate precisely so that guessing is never
rewarded over handing off.
