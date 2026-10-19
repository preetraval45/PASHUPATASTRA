# SatiProviderOwnModels

- **Date:** 2026-10-18
- **Phase:** Block H — RP-63; product without external LLMs
- **Commit(s):** this push

## What changed

- The owner decided Ollama is out of the product but stays as a benchmark
  baseline, and that chat answers come from the project's own models only.
- services/api/app/engines/providers/sati.py has SatiProvider (structured_evidence=True).
  - general_answer_v1: Brahmacharini retrieval over knowledge.json /
    knowledge.vec, with an "outside what Sati knows" message under
    RELEVANT=0.28, and a HARMFUL regex that sets declined.
  - chat_answer_v1: starters map to evidence sources (chain / hypothesis /
    plan / incident). Anything else is ranked by cosine. It never proposes
    actions.
- Core gateway.converse passes the evidence plus a "visitor" item when the
  provider has structured_evidence.
- sati.embed.export trains the serving model (2^15 buckets, width 128,
  dim 96, int8) and writes services/api/app/sati_models/*. The brahmacharini
  CI job runs it and commits the artefacts.
- deploylambda: when PASHU_MODEL_PROVIDER=sati it sets sati and drops the
  third-party key.
- 2026-10-18: production was deployed with root `aws login` credentials
  (profile `pashupatastra`). The DynamoDB table `pashupatastra` was created
  (it was missing, which is why storage had been memory-only). Health is now
  ok with dynamodb storage, and all routes return 200.

## Next session should

- Once train-sati has committed sati_models, rebuild and deploy with
  PASHU_MODEL_PROVIDER=sati. Then check /agent/ask and /agent/chat live.
- Replace root credentials with a scoped deploy role and recommend MFA.
- Kushmanda v1: a proper LLM (RoPE/RMSNorm/SwiGLU, dedup, SFT, constrained
  JSON). Notebooks per model, as requested by the owner.
