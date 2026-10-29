# Model card — Kushmanda v2 (`sati-kushmanda-v2`)

Format follows Mitchell et al. (2019). The generated table
[kushmanda.md](../kushmanda.md) is the source of truth. The numbers below are
a snapshot of the Kaggle GPU run of 26 October 2026, at commit `74cc4ee`.

## Model details

- **What it does:** answers a security question **from the passages it is
  given**, cites the passage it used (`[2]`), and says "The context does not
  answer this" when none holds the answer. Model 4 of the nine
  ([adr/Navadurga](../../../adr/Navadurga.md)), Sati's own language model.
- **Type:** a decoder-only transformer written from scratch in PyTorch,
  trained from random initialisation, with 16.9M parameters:
  - architecture: 6 layers, width 384, 6 heads, context 640, dropout 0.1;
    RMSNorm, rotary positions, SwiGLU, fused causal attention and tied
    embeddings;
  - tokenizer: its own byte-level BPE with 16,384 tokens.
- **Training:**
  - **pretraining:** 4,000 steps over 32.2M tokens (about 5.1 passes) with
    AdamW, warmup plus cosine decay and gradient clipping;
  - **instruction tuning:** 3,000 steps of grounded tuning, with loss on the
    answer only.

  The best checkpoint is chosen on held-out loss.
- **Built by:** an AI assistant (Claude), under the owner's direction.
- **Weights:** 68 MB, stored as a **private** Kaggle Model
  (`preetraval4518071604/sati-kushmanda`, PyTorch instance `v2`: weights,
  tokenizer and results), not in git. Every source permits release
  ([datasheets.md](../../datasheets.md)), so they are Apache-2.0 eligible.
  Making them public is the owner's decision.
- **Serving without PyTorch:** `sati.lm.infer` runs the same forward pass in
  numpy with a key/value cache, from int8 weights (about 17 MB). CI checks it
  against PyTorch: logits and greedy output are identical unquantised, and
  quantised logits correlate above 0.99.

## Intended use

- **For:** composing an answer from evidence Sati has already retrieved
  (Brahmacharini's passages), with a citation a verifier can check (rule 1).
- **Out of scope:**
  - answering from memory;
  - returning an exact identifier unchecked. On ID questions, simple word
    overlap beats it (see below), so an ID it produces must be checked
    against the cited passage before it is shown;
  - anything outside the security knowledge it was trained on.

## Data

| Source | Documents |
|---|---:|
| NVD CVE descriptions (new in v2) | 343,686 |
| ATT&CK procedure examples | 14,431 |
| ATT&CK techniques | 3,652 |
| CISA KEV | 1,686 |
| CAPEC | 1,207 |
| CWE | 917 |
| This repository's docs | 282 |

After cleaning and MinHash deduplication: 365,861 documents, of which 18,410
are held out by document. Instruction pairs number 22,608 for training and
1,462 for testing, held out **by entity**: every test question is about a
technique, CVE or CWE that never appears in tuning.

## Metrics

**Language modelling (held-out documents):** loss 2.1186, perplexity 8.32,
0.756 bits per byte. Held-out loss was still falling at the last step. The
corpus and held-out set differ from v1's, so the two perplexities are not
comparable.

**Answering from given passages (1,200 held-out questions):**

| Question | Measure | Kushmanda v2 | Word-overlap baseline | Chance |
|---|---|---:|---:|---:|
| Define a technique, CWE or CVE | ROUGE-L | **0.785** | 0.683 | 0.321 |
| What to do about a CVE | ROUGE-L | **0.938** | 0.361 | 0.258 |
| Mitigations for a technique | ROUGE-L | **0.998** | 0.613 | 0.264 |
| No passage holds the answer | declined | **0.543** | 0.000 | 0.000 |
| Technique ID by name | exact match | 0.528 | **0.962** | 0.396 |
| Behaviour → technique (3 candidates) | exact match | 0.423 | **0.690** | 0.305 |

## What the numbers say

- **v2 does the job v1 could not.** v1 scored 0.000 on the same kind of
  held-out entities, because it was asked to recall facts with no context.
  Answering from passages is a task a 17M-parameter model can learn.
- **It writes answers well and copies identifiers badly.** On free-text
  answers it beats the baseline by 0.1 to 0.6 ROUGE-L. On questions whose
  answer is one ID, it is worse than simple word overlap. A model this small
  does not reliably copy a 9-character string. So in Sati, an ID must be
  verified against the cited passage, or taken from retrieval directly.
- **Declining half the time is not enough on its own.** It declines on 54% of
  unanswerable questions and wrongly declines on 0–13% of answerable ones,
  depending on question type. The remaining 46% are fabricated answers, and
  citation checking must catch them.
- **Constraining fixes the form, not the choice** ([kushmanda-constrained.md](../kushmanda-constrained.md)).
  When decoding may only write an identifier from the passages, every output
  is valid (1.000, against 0.993 free). Lookup exact match rises from 0.528 to
  0.604, still far below word overlap's 0.962. Behaviour → technique barely
  moves (0.423 to 0.432). The model's remaining errors are in choosing which
  identifier, so in serving the identifier comes from retrieval.
- **Twice the size copies identifiers better and declines less** ([kushmanda-v3.md](../kushmanda-v3.md)).
  v3 has 34.1M parameters and a corpus that adds GitHub Security Advisories.
  On the same 1,200 held-out questions, it raises lookup exact match from
  0.528 to 0.717 and behaviour → technique from 0.423 to 0.567. Definitions
  rise from 0.785 to 0.827 ROUGE-L. But it declines on only 0.417 of
  unanswerable questions, against 0.543, and loses a little on required
  actions (0.896) and mitigations (0.946). It is still below word overlap on
  identifiers (0.962 and 0.690). v2 stays served: declining when no passage
  answers matters more in Sati than a better identifier, which comes from
  retrieval anyway.

## Known limitations

- The questions are templated from structured sources, so real users'
  phrasing will be harder.
- No safety tuning beyond grounding: harmful-request refusal stays in Sati's
  serving layer (`providers/sati.py`).
- Greedy decoding is used for evaluation; sampling is not evaluated.

## Ethical considerations

The data is public security text under permissive terms; no personal data is
included. Generation is defensive: definitions, required actions and
mitigations.
