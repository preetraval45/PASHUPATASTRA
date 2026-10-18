# LLM baselines — a 2 × 2 that changes one thing at a time

- **Status:** Accepted · 18 October 2026 (RP-06; drafted by Claude, plan defaults applied at the owner's instruction to proceed)
- **Date:** 2026-10-18
- **Phase:** Research plan, Block A

## Context

The paper claims that the *architecture* (Dharma's policy gate and the
verification stage) matters, separately from *how smart the proposer is*. If
only the naive arm used a language model, the comparison would change two
things at once: the proposer and the policy layer. A difference could then
come from either.

Since 18 October the general LLMs are also the **baseline the project's own
models must beat** ([RealDataModels](RealDataModels.md),
[Navadurga](Navadurga.md)). They are never the brain.

## Decision

**A 2 × 2, plus Sati as a third proposer row later (RP-28 / RP-63):**

| | No policy, no verification | Dharma + verification |
|---|---|---|
| **Deterministic proposer** | `runbook` | `pashupatastra` |
| **LLM proposer** | `naive-llm` | `pashupatastra-llm` |
| *Sati models (later)* | — | `pashupatastra-sati` |

Rows isolate the proposer and columns isolate the architecture.

**The LLM proposer**
- It sees the same `Brief` as every arm: live observed state, the allowed
  actions and the risk ceiling. It never sees the scenario's expected answer.
- It returns a validated `proposal_v1` (rule 4) naming **one** of: an allowed
  action, `do_nothing`, or `escalate`. Anything else is rejected.
- It goes through the AI Gateway (rule 5) to the self-hosted Ollama endpoint.
  The token comes from the environment and is never in the repository.
- Its failures are graded separately from wrong answers. A provider or schema
  failure is recorded with cause `llm_error`, and an off-list proposal with
  cause `off_list`, so the table can tell "chose badly" from "could not answer".

**Models and temperature** (the plan's defaults, applied when the owner asked
for the tasks to proceed; changeable here before RP-09 runs):

| Setting | Value |
|---|---|
| Models | `qwen2.5:7b`, `mistral` (7B), `llama3` (8B) |
| Temperature | 0.2, recorded per run with the seed |
| Runs | N = 3 per scenario, the same as every other arm |

**Both LLM arms refuse to run against the deterministic stub.** An LLM baseline
answered by a fixture would be fabricated, so the arm stops and says why
instead.

## Consequences

**Enables:**
- Table 1 with all four cells.
- The significance tests in RP-10, which ask whether the policy layer helps
  *given an LLM proposer*.
- The bar that the Sati models have to clear.

**Rules out:**
- Comparing an LLM-with-tools to a runbook and calling the gap "the
  architecture".
- Silently mixing provider errors into accuracy.

**Revisit when:** the owner picks different models or temperature, or a Sati
proposer exists. That adds a row; it doesn't change this one.
