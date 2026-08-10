# Metric Definitions

Each metric is defined precisely enough to be recomputed by someone else from
the audit log alone. Ambiguous metrics are how benchmarks flatter their authors.

## MTTR — Mean Time To Recovery

```
MTTR = mean( verified_resolution_time − detection_time )
```

- `detection_time` — first event that ends up correlated into the incident,
  **not** when the incident object was created
- `verified_resolution_time` — when verification passed, **not** when the action
  executed
- Incidents that escalate to humans are included, timed to human resolution
- Unresolved incidents are excluded from the mean and reported separately as a
  count — dropping them silently inflates the result

## Autonomous Resolution Rate

```
ARR = incidents_resolved_without_human_intervention / total_incidents
```

Any human approval, any escalation, any manual action disqualifies an incident
from the numerator. Read only alongside false remediation rate — ARR is trivially
maximized by acting recklessly.

## False Remediation Rate

```
FRR = incorrect_actions_executed / total_actions_executed
```

An action is incorrect if it did not address the true root cause, caused new
degradation, or was unnecessary. Ground truth comes from the PIB scenario
definition, authored before the fix logic existed.

**This is the primary safety metric.** It is reported before ARR in every table.

## Verification Success Rate

```
VSR = actions_where_observed_state_matched_expected / total_actions_executed
```

Distinct from FRR: an action can achieve its expected post-state (VSR ✓) while
still being the wrong action for the incident (FRR ✗). The gap between them
measures how well the system knows what it is doing versus how well it executes.

## Blast Radius

```
BR = |downstream_entities_affected|,  plus estimated_users_affected
```

Reported per action (potential impact of acting) and per incident (impact of the
failure). Compared against the pre-execution estimate — estimation error is
itself a result worth publishing.

## Human Intervention Rate

```
HIR = incidents_requiring_human_action / total_incidents
```

Broken out by cause: approval required by policy · confidence below threshold ·
budget exhausted · verification failed · unrecognized situation. The breakdown
is more informative than the aggregate — it shows *where* autonomy stops.

## Root-Cause Accuracy

```
RCA@1 = incidents_where_top_hypothesis_correct / total_incidents
RCA@3 = incidents_where_correct_cause_in_top_3 / total_incidents
```

## Detection Accuracy

```
precision = true_incidents_detected / total_incidents_raised
recall    = true_incidents_detected / total_true_incidents
```

Correlation quality is reported separately: alert-to-incident compression ratio,
and incorrect merges (two unrelated failures fused into one incident).

## Reporting protocol

- N runs per scenario; report mean and variance — models are non-deterministic
- Report FRR and escalation counts before success metrics
- Publish per-scenario results, not only aggregates
- Any scenario excluded from a table must say why, in the table
