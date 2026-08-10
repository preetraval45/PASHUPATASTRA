# Specification — Dharma Policy Model (v0)

**Status:** Draft. Not yet implemented. Lands in Phase 3.

## Purpose

Bounded autonomy: the AI may act, but only inside operationally defined
boundaries. Dharma is the component that makes "safe" a property of the
architecture rather than a promise in the prompt.

## The core rule

> **Astra cannot execute without a Dharma verdict.**

Enforced structurally — the execution API requires a signed verdict object as an
argument. There is no code path, including test fixtures and dev tooling, that
reaches a connector's write API without one. This is verified by a red-team pass
as the Phase 3 exit criterion.

## Risk scoring

Every registered action declares a base risk score.

| Action | Risk |
|--------|-----:|
| Read logs / metrics | 0 |
| Restart service | 10 |
| Scale deployment | 20 |
| Clear cache | 30 |
| Rollback deployment | 45 |
| Change DB configuration | 65 |
| Delete infrastructure | 100 |

Effective risk is the base score adjusted by context:

```
effective_risk = base_risk
               + blast_radius_penalty     (downstream services & users)
               + environment_penalty      (prod > staging > dev)
               + confidence_penalty       (low diagnostic confidence raises risk)
               + novelty_penalty          (never executed here before)
```

Adjustments only ever raise risk. Nothing lowers a declared base score — an
action cannot argue its way into a lower tier.

## Autonomy tiers

| Effective risk | Authority |
|---------------|-----------|
| 0–30 | Autonomous |
| 31–60 | Approval required |
| 61–80 | Senior approval |
| 81–100 | Never autonomous |

**Hard overrides**, regardless of computed score:

- Blast radius above the configured threshold escalates one tier
- Destructive/irreversible actions cap at "never autonomous"
- An action with no tested rollback cannot be autonomous
- Dry-run is the default; live execution is opt-in per environment
- An agent may never exceed its own configured `risk_limit`

## Verdict

```
Verdict
├── action_ref
├── incident_ref
├── effective_risk        with the full adjustment breakdown
├── tier                  autonomous | approval | senior | denied
├── required_approvers[]
├── granted_by            agent identity or human principal
├── expires_at            verdicts are short-lived; stale ones are invalid
└── constraints           scope limits applied to the execution
```

Verdicts expire. A plan approved during an incident cannot be replayed later
against a different system state.

## Audit

Every evaluation is recorded whether or not it resulted in execution — including
denials. Denials are the most interesting records for the research: they
document where autonomy stopped and why.
