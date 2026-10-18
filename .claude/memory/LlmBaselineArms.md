# LlmBaselineArms

- **Date:** 2026-10-18
- **Phase:** Block A — RP-06 done, RP-07 built
- **Commit(s):** this push

## What changed

- adr/LLMBaselines.md: the 2 × 2, with the plan defaults applied (qwen2.5:7b,
  mistral, llama3; temperature 0.2; N = 3).
- benchmark/harness/llm.py: LLMProposer and baseline_gateway. The env vars are
  PASHU_BASELINE_BASE_URL, PASHU_BASELINE_API_KEY, PASHU_BASELINE_MODEL and
  PASHU_BASELINE_TEMPERATURE. The provider comes from
  services/api/app/engines/providers/openaicompat.py, which now takes a
  `temperature` (default 0).
- Arms: NaiveLLMArm(proposer). PashupatastraArm(proposer=...) is the
  `pashupatastra-llm` cell, with the same Dharma, Remediator and verification.
  Arm.PASHUPATASTRA_LLM was added to core. run.py probes the LLM arms by
  building them, never by calling the model.
- The proposal_v1 schema is in providers/schemas.py.
- CI's core job now runs benchmark/harness tests (25).

## Decisions made

- Errors go to cause `llm_error`, off-list proposals to `off_list`, model
  escalations to `model_escalated`. All three are safe, and all are counted
  apart from wrong answers.

## Next session should

- RP-09 needs the owner's Ollama endpoint and token as PASHU_BASELINE_*,
  ideally as GitHub secrets so the run happens on Actions alongside the kind
  cluster.
