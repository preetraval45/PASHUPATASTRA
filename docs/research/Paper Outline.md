# Paper Outline

## Working title

**Pashupatastra: Policy-Constrained Closed-Loop Autonomous Infrastructure
Operations**

## Research question

> Can an AI system safely perform autonomous infrastructure remediation by
> combining observability, causal reasoning, historical incident memory, policy
> constraints, and post-action verification?

Note the load-bearing word: **safely**. The interesting result is not that an
agent can restart a service — it is the shape of the boundary where autonomy
should stop, and whether that boundary can be defined operationally rather than
by intuition.

## Contribution claims

1. **An architecture** for closed-loop infrastructure autonomy that separates
   reasoning (probabilistic) from authorization (deterministic).
2. **Bounded autonomy formalized** — risk scoring with context adjustment,
   autonomy tiers, and structural enforcement that no execution path bypasses.
3. **PIB**, a reproducible incident benchmark with expected diagnoses, expected
   actions, and expected recovery states.
4. **An empirical comparison** of human, runbook automation, naive LLM agent,
   and the full architecture — reporting false remediation rate as prominently
   as success rate.
5. **Post-action verification as a first-class stage**, with evidence that it
   catches wrong remediations that confident diagnosis does not.

## Structure

1. **Introduction** — complexity outpaces dashboard-and-alert operation
2. **Background & related work** — AIOps, LLM agents, runbook automation,
   causal inference in systems, safe RL / constrained agency
3. **Architecture** — the loop; Drishti / Smriti / Buddhi / Astra / Dharma /
   Kavach; knowledge graph; AI Gateway
4. **Bounded autonomy** — risk model, tiers, verdicts, structural enforcement
5. **Verification & learning** — expected post-state contracts, rollback,
   outcome feedback into memory
6. **PIB** — scenario design, fault injection, baselines, protocol
7. **Evaluation** — metrics, results, ablations
8. **Ablations** — the experiments that make it credible:
   - without evidence-requirement on hypotheses
   - without Smriti retrieval
   - without topology-adjacency correlation
   - without verification stage
   - without policy tiers (naive agent)
9. **Discussion** — where autonomy should stop; failure analysis; what the
   escalation cases have in common
10. **Limitations & threats to validity**
11. **Conclusion & future work** — Kaal simulation, physical systems

## Threats to validity — state these plainly

- **Self-authored benchmark.** Mitigation: scenarios authored before the fix
  logic; scenario definitions published; false remediation reported first.
- **Synthetic incidents differ from production.** Mitigation: fault injection
  against a real containerized stack, not telemetry replay, wherever feasible.
- **Model non-determinism.** Mitigation: N runs per scenario, variance reported.
- **Single reference architecture.** Generality is a claim the benchmark cannot
  fully support; say so.

## Target venues

Systems and operations venues over ML venues — the contribution is
architectural and empirical, not a new model. SoCC, OSDI/ATC workshops, SREcon,
or an arXiv preprint paired with the open-source release.

## Timeline

Drafted alongside Phase 5; submitted at Phase 6 with the code and benchmark
public, so results are reproducible on release day.
