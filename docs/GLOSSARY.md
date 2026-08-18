# Glossary

## Subsystems

| Term | Meaning |
|------|---------|
| **Drishti** (दृष्टि, *vision*) | Perception engine. Connectors + normalization + topology construction. |
| **Smriti** (स्मृति, *memory*) | Organizational memory. Past incidents, fixes, decisions, runbooks; hybrid retrieval. |
| **Buddhi** (बुद्धि, *intellect*) | Reasoning engine. Anomaly detection, correlation, causal hypotheses, blast radius. |
| **Astra** (अस्त्र, *weapon*) | Action engine. `Autonomous System Tactical Response Architecture`. Plans, executes, rolls back. |
| **Kavach** (कवच, *armor*) | Security. Detection and correlation of adversarial signals. Defensive only. |
| **Dharma** (धर्म, *law*) | Policy engine. Risk scoring and bounded-autonomy enforcement. |
| **Kaal** (काल, *time*) | Simulation / digital twin. "What happens if…" before acting. |
| **Sati** (स्मृति/सति, *mindfulness, recollection*) | **The AI agent.** The reasoning actor that observes, investigates, proposes, and — within Dharma's bounds — acts. |

Names are load-bearing in code — module prefixes, not decoration. Brand tone is
"ancient concept → modern intelligence"; no religious or fantasy imagery.

### Sati and the engines

The engines are capabilities. **Sati is the actor that uses them.** Drishti
perceives, Buddhi reasons, Smriti remembers, Astra executes; Sati is what decides
which to reach for, in what order, and when to stop and ask a human.

The distinction is not cosmetic, and it decides where code goes. An engine is
deterministic, testable in isolation, and has no opinion about what to do next.
Sati is the part that has opinions — and is therefore the part that must never be
trusted without evidence, must carry a budget, and must pass every action through
Dharma. Keeping the boundary sharp is what makes "the LLM is not the source of
truth" enforceable rather than aspirational: the engines hold the truth, Sati
holds the reasoning, and only Dharma authorises the consequence.

Sati is a single identity with specialised roles rather than a fleet of separate
products — `sati.sentinel` triages, `sati.hunter` hunts, `sati.analyst`
reconstructs. Each is an `AgentSpec` with its own tools, budget and risk ceiling.
The name is chosen for *recollection under attention* — the discipline of holding
what was seen and checking it, which is exactly what separates an investigator
from a generator.

## Concepts

| Term | Meaning |
|------|---------|
| **The loop** | `Observe → Understand → Predict → Decide → Act → Verify → Learn`. |
| **Bounded autonomy** | AI may act only inside operationally defined risk boundaries. The thesis of the project. |
| **Blast radius** | Graph-computed set of downstream entities and users affected by a failure or an action. |
| **Verdict** | Dharma's short-lived authorization object. Required argument to any execution. |
| **Expected post-state** | The state an action claims it will produce. Declared before execution; compared after. |
| **Verification** | Comparing observed post-state to expected post-state. Failure triggers rollback. |
| **Causal chain** | Ordered, evidence-cited sequence of entity state transitions explaining an incident. |
| **Provenance** | Reference letting a human retrieve the original record behind any claim. |
| **Escalation** | Handing control to a human. A success outcome, not a failure. |
| **AI Gateway** | Vendor-neutral model access layer. The only place a model SDK is imported. |

## Metrics

| Term | Meaning |
|------|---------|
| **MTTR** | Mean time to recovery — detection to verified resolution. |
| **Autonomous resolution rate** | Share of incidents resolved with no human intervention. |
| **False remediation rate** | Share of executed actions that were incorrect. The number that matters most. |
| **Verification success rate** | Share of actions where expected state was actually achieved. |
| **Human intervention rate** | How often a human had to step in. |

Defined precisely in [research/METRICS.md](research/METRICS.md).

## Benchmark

| Term | Meaning |
|------|---------|
| **PIB** | Pashupatastra Incident Benchmark — 100–500 controlled incidents with expected diagnosis, action, and recovery state. |
| **Scenario** | One PIB incident definition. |
| **Baseline** | Comparison arm: human, runbook automation, naive LLM agent, Pashupatastra. |
