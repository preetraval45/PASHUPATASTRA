# Sati notebooks

Two kinds, kept apart:

- **`models/`** — one notebook per trained Sati model, written by Claude at the
  owner's request (18 October 2026). Each one explains the data, features and
  model, then runs the real pipeline end to end on Kaggle or Colab — clone,
  install, load the real data, train, evaluate against the baselines, plot.
  They mirror the committed results tables in `docs/research/models/`.

  | Notebook | Model |
  |---|---|
  | `01-katyayani-root-cause.ipynb` | Katyayani — root cause on RCAEval |
  | `02-shailaputri-anomaly-detection.ipynb` | Shailaputri — anomalies on NAB |
  | `03-kalaratri-log-anomalies.ipynb` | Kalaratri — log anomalies on LogHub HDFS |
  | `04-brahmacharini-embeddings.ipynb` | Brahmacharini — behaviour → ATT&CK technique |
  | `05-kushmanda-language-model.ipynb` | Kushmanda — Sati's own language model (GPU) |

- **This folder's root** — the owner's own learning work (RP-02 and on), which
  stays the owner's: Claude reviews it for bugs and leakage and does not
  write it.

## RP-02 — Learn transformers by building one

- [ ] Karpathy, *Let's build GPT: from scratch, in code, spelled out*
      (*Neural Networks: Zero to Hero*). Type every line; don't paste.
      Save as `gpt.ipynb` here.
- [ ] Jay Alammar, *The Illustrated Transformer*
      — jalammar.github.io/illustrated-transformer
- [ ] Vaswani et al. 2017, *Attention Is All You Need*, §3 only
      — arXiv:1706.03762
- [ ] The notebook trains a tiny character-level GPT and generates text.
      Keep the generated sample in the committed output.
- [ ] `transformers.md` here: one page, your words —
      tokens → embeddings → attention → next-token distribution.

Run it on Kaggle or Colab (free, in the browser), then download the `.ipynb`
and commit it. Nothing here needs your PC.

**Before you ask for review, check yourself on:**

- Is the causal mask applied *before* the softmax, so position *t* cannot see
  *t + 1*?
- Are train and validation split by position in the text, not shuffled
  characters?
- Why scale attention scores by `1/sqrt(head_size)`? What breaks without it?
- What do the residual connections and layer norm each fix?

When both files are in, say *"review RP-02"*. RP-02 is ticked after that review.
