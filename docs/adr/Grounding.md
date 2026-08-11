# The LLM is not the source of truth

- **Status:** Accepted
- **Date:** 2026-08-10
- **Phase:** Phase 0

## Context

The obvious build is: give a capable model tool access to infrastructure and let
it reason its way to a fix. It demos well and it is fast to stand up. It is also
the design that makes the product unshippable to anyone with a production
system, because a confident wrong answer executes exactly as smoothly as a
correct one.

The differentiating claim of this project is safety under autonomy. That claim
cannot be made by a system where a model's free-text output is the control
signal.

## Decision

The model proposes; deterministic components dispose. Concretely:

1. **Hypotheses require evidence.** A causal hypothesis that cannot cite the
   telemetry supporting it is suppressed, not surfaced at low confidence.
2. **Actions come from a closed registry**, never from parsed model text. The
   model selects an action ID; it does not author a command.
3. **Authorization is deterministic code.** Dharma computes risk and issues
   verdicts. No model call participates in authorization.
4. **All model output is a validated structured schema.** No free-text parsing
   anywhere in the control path.
5. **All model access goes through the AI Gateway.** No vendor SDK import in
   engine code.
6. **Verification is observational**, not model-judged. Expected post-state is
   compared against observed telemetry.

## Consequences

**Enables:**
- Provenance for every operator-facing claim
- A safety argument that survives adversarial review
- Vendor swap without touching engine logic
- Prompt-injection resistance — untrusted telemetry cannot become an instruction

**Rules out:**
- Free-form "just run this command" capability, permanently
- Shell or raw cloud-credential access from any model-reachable tool
- Rapid capability growth by prompt alone — new actions require registry entries
  with risk scores, expected post-states, and tested rollbacks

**Revisit when:**
- Never for items 2–4. Item 1's confidence threshold is tunable with benchmark
  evidence.

## Alternatives considered

- **Model with shell access, human approval on everything** — approval fatigue
  makes the human a rubber stamp, so the safety is illusory while the blast
  radius is unbounded.
- **Model-judged verification** — the same system that produced the wrong fix
  grades whether the fix worked. Circular.
