# Pre-declared run matrix — LLM baselines (RP-09)

Committed **before any LLM baseline result exists**, as RESEARCH PLAN.md rule 3
requires. Results that deviate from this matrix are reported as deviations,
never quietly re-run until they look better.

| Setting | Value | Source |
|---|---|---|
| Scenarios | the 31 executable PIB scenarios (20 negative, 6 escalation, 5 remediate) | `benchmark/incidents/pib`, harness coverage |
| Arms | `naive-llm` (no policy, no verification), `pashupatastra-llm` (Dharma + Remediator + verification) | [adr/LLMBaselines](../../adr/LLMBaselines.md) |
| Models | `qwen2.5:7b`, `mistral` (7B), `llama3` (8B), Ollama default quantisation | the ADR |
| Temperature | 0.2, recorded per run | the ADR |
| Runs | N = 3 per scenario per arm per model, resumable | the plan |
| Hardware | GitHub Actions `ubuntu-latest`, CPU only (4 vCPU, 16 GB), recorded in every run record | `.github/workflows/benchmark.yml` |
| Fallback | **none.** An LLM failure is recorded as `llm_error`, never answered by another model | the ADR |
| Grading | the existing PIB verdicts; LLM errors and off-list proposals are counted apart from wrong answers | `scripts/papertables.py` |
| Significance | McNemar exact test and a paired bootstrap on false-remediation rate, resampling scenarios (RP-10) | `pashupatastra.significance` |

Total: 31 × 2 × 3 × 3 = **558 runs**, in six parallel jobs. The comparisons
are fixed in advance:

- `pashupatastra-llm` vs `naive-llm`, per model: the policy layer's effect,
  given an LLM proposer.
- `naive-llm` vs `runbook`: the proposer's effect without policy.
- `pashupatastra-llm` vs `pashupatastra`: the proposer's effect with policy.

**Deviation already known:** the plan named the Oracle box as the endpoint.
These runs use Ollama on GitHub's runners, also CPU-only, because nothing may
run on the owner's PC and the Oracle endpoint's secrets aren't set. The model
weights and quantisation are the same Ollama defaults either way.
