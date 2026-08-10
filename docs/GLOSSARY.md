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

Names are load-bearing in code — module prefixes, not decoration. Brand tone is
"ancient concept → modern intelligence"; no religious or fantasy imagery.

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
