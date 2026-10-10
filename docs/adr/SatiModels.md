# Sati models — the models Sati runs on, trained here

- **Status:** Proposed — drafted by Claude for RP-04; three owner decisions open (below)
- **Date:** 2026-10-10
- **Phase:** Research plan, Block A

## Context

[CLAUDE.md](../../CLAUDE.md) and [GLOSSARY.md](../GLOSSARY.md) define **Sati as
the agent**: the reasoning actor that chooses which engine to use and when to
ask a human. Today it reasons through general-purpose LLMs reached via the AI
Gateway.

On 9 October 2026 the goal changed: Sati should run on models designed and
trained in this repository (see [RESEARCH PLAN.md](../research/RESEARCH%20PLAN.md)).
Calling those models "Sati" changes what the name means, so it is decided
here rather than assumed. Three things are at stake:

1. **The name.** If "Sati" means both the agent and a model, a reader can no
   longer tell whether a claim is about the decision loop or about one
   classifier inside it.
2. **The boundary.** Training needs PyTorch. `packages/core` must stay
   dependency-light and laptop-runnable ([Platform](Platform.md)).
3. **The rules.** A model trained here is still a model. Rules 1, 2, 4 and 5
   in CLAUDE.md apply to it as they do to an LLM.

## Decision

**Sati remains the agent. "Sati models" are the models it runs on.** The agent
is one identity; the models are interchangeable parts it calls through the
Gateway. A sentence about *Sati* is about the agent. A sentence about a model
names the model.

**The model family**

| Model | Job | Replaces |
|---|---|---|
| **Sati-Detect** | Anomaly scoring on metrics | statistical strategies, where it measurably beats them (RP-23) |
| **Sati-RCA** | Ranks root-cause service and fault type, citing event IDs | LLM diagnosis |
| **Sati-Embed** | Incident text → vectors for Smriti recall | `HashingEmbedder`, if it wins (RP-30) |
| **Sati-LM** *(stretch)* | Writes the structured hypothesis | LLM hypothesis writing |

**Where the code lives**

- `packages/sati/` — model code, training, notebooks, its own dependencies
  (PyTorch, LightGBM). Owner-written; Claude reviews.
- `packages/core` — **stays torch-free.** It knows the *interfaces*
  (`DetectionStrategy`, `Embedder`, the hypothesis schema), never a model.
- `services/api/app/engines/providers/sati.py` — serves trained artefacts as a
  Gateway provider (RP-28). Engines never import a model directly (rule 5).

**How they are served**

- A Sati model is a Gateway **provider**, selected by configuration like any
  other, and returns the same validated schema (rule 4).
- Artefacts are versioned and hashed; every response and audit record carries
  `provider` and `model_version` (rule 6).
- Failover is **Sati primary → Oracle Ollama backup**, and every fallback answer
  is labelled with the provider that produced it. **Benchmark runs never fall
  back**: a Sati failure is recorded as a Sati failure.
- Sati proposes, Dharma authorises. A model trained here gets no exemption from
  policy (rule 2), and Sati-RCA's answers must pass the same citation
  verification as an LLM hypothesis (rule 1).

**LLMs are baselines, not the brain.** General-purpose LLMs stay in the system
in two roles only: the comparison Sati models must beat, and the labelled
fallback.

**Contamination rules**

1. PIB, the 20 labelled incidents and the external benchmark are **test-only**.
   No training or tuning on them. A guard fails the build on any match (RP-18).
2. Splits are by **topology** and by **fault type**, never random.

## Owner decisions — open

These are the owner's, and the ADR is not Accepted until they are filled in.

- **Names.** Keep `Sati-Detect`, `Sati-RCA`, `Sati-Embed`, `Sati-LM`? *(decision: …)*
- **Weights.** Release trained weights publicly, privately, or not at all? *(decision: …)*
- **Licence for weights.** The repository has no licence yet (README). Released
  weights need one; code and weights may differ. *(decision: …)*

## Consequences

**Enables:**
- A paper contribution that is the owner's own: a purpose-trained diagnostic
  model against general LLMs, under the same policy layer.
- Citations by construction: a feature-based model knows which event IDs each
  feature came from, which an LLM cannot guarantee.
- Running with no third-party model at all, on CPU, for the trained models.

**Rules out:**
- Importing torch, or any model, into `packages/core`.
- Using "Sati" alone to mean a model.
- Any "the model said so" path: a Sati model's answer goes through citation
  verification and Dharma like everything else.

**Revisit when:**
- Sati-RCA does not beat the LLM baselines on held-out topologies (RP-29). The
  agent/model split stands either way; what Sati runs on by default may not.
- Sati-LM becomes viable and the agent no longer needs an external LLM at all.

## Alternatives considered

- **Give the models non-Sati names** — clearer separation, but the owner's goal
  is that Sati runs on *its own* models; the prefix states that ownership while
  "Sati" alone stays the agent.
- **Rename the agent** — touches every page, the glossary and the brand, to
  solve a naming collision a suffix already solves.
- **Put models in `packages/core`** — breaks the laptop-runnable, dependency-light
  boundary in [Platform](Platform.md).
- **Fine-tune an open LLM instead of training** — faster, but not the owner's
  own model, and it moves the contribution away from what the paper claims.
  Kept possible as a baseline.
