# Sati notebooks

The owner's learning and model notebooks. Everything in this folder is written
by the owner. Claude reviews it for bugs and leakage, and does not write it
(RESEARCH PLAN.md, *How to use this plan*).

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
