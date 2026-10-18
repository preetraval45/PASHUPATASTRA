# Kushmanda

- **Date:** 2026-10-18
- **Phase:** Block H — RP-65 (and RP-41 to RP-43 brought forward)
- **Commit(s):** this push

## What changed

- packages/sati/sati/lm/: corpus.py (MITRE ATT&CK enterprise and CAPEC STIX,
  CISA KEV, the repo's docs and training.ts; a deterministic hash split by
  document), model.py (a from-scratch GPT: pre-norm blocks, causal mask, tied
  head, generate), train.py (BPE tokenizer via `tokenizers`, AdamW with
  cosine schedule, held-out loss / ppl / bits-per-byte, comparison with GPT-2
  tokens-per-line via tiktoken, samples, saved .pt) and report.py.
- kaggle/kushmanda/run.py runs on Kaggle: it clones at the commit, pip
  installs tokenizers and tiktoken, then runs sati.lm.train.
- .github/workflows/kaggle-kushmanda.yml is gated on KAGGLE_API_TOKEN and
  KAGGLE_USERNAME. It pushes the kernel (private, GPU, internet), polls the
  status, downloads the output, and commits the results.
- The train-sati test job installs CPU torch for testlm.py.

## Why

The owner asked for all AI to be their own, and for their own models to be
built. Kushmanda is the language model that would replace the external LLM.

## Decisions made

- Permissively licensed text only, so the weights can be Apache-2.0. LogHub
  stays out.
- Bits per byte is reported because perplexity is not comparable across
  tokenizers.

## Open questions

- The owner pasted a Kaggle token into the chat. They were told to add it as a
  GitHub secret and to regenerate it. Claude did not write it anywhere.
  KAGGLE_USERNAME is still needed. GPU on Kaggle requires a phone-verified
  account.

## Next session should

- Once the secrets exist, watch the first Kaggle run. Then RP-44: fine-tune on
  the hypothesis JSON with constrained decoding before Kushmanda answers in
  Sati AI.
