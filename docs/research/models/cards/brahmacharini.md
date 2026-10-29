# Model card — Brahmacharini v0 (`sati-brahmacharini-v0`)

Format follows Mitchell et al. (2019). The generated table
[brahmacharini.md](../brahmacharini.md) is the source of truth.

## Model details

- **What it does:** maps a description of observed behaviour to the MITRE
  ATT&CK technique it describes. It also retrieves the knowledge passages
  behind every answer Sati AI gives ([adr/SatiEmbed](../../../adr/SatiEmbed.md)).
  It is one of the nine Sati models
  ([adr/Navadurga](../../../adr/Navadurga.md)).
- **Type:** a dual encoder written from scratch in PyTorch:
  - text is split into hashed word unigrams and bigrams;
  - an `EmbeddingBag` takes their mean, followed by a linear projection and L2
    normalisation;
  - the result is a 128-dimensional embedding.

  The same encoder reads both the behaviour and the technique. It is trained
  with InfoNCE, using the other techniques in each batch as negatives. The
  epoch is chosen by validation MRR.
- **Served version** (`sati-brahmacharini-serve-v0`): the same design, smaller,
  so it fits the API's lean Lambda archive:
  - 32,768 hash buckets, width 128, 96 dimensions;
  - quantised to int8 with one scale per row;
  - run in pure Python, without PyTorch or NumPy.

  It is combined with BM25 into a hybrid score, and it declines to answer below
  a set relevance threshold.
- **Built by:** an AI assistant (Claude), under the owner's direction.
- **Weights:** the served int8 weights are committed in
  `services/api/app/sati_models/`. They were trained only on MITRE content,
  which MITRE licenses royalty-free.

## Intended use

- **For:**
  - retrieving ATT&CK, CAPEC and CISA KEV passages to ground Sati AI's answers;
  - suggesting candidate techniques for a behaviour an analyst has seen.
- **Out of scope:**
  - generating text;
  - answering anything outside that knowledge base. Sati AI declines instead.
  - acting as a classifier whose top answer is trusted without review.
    Recall@1 is 0.61, so about two answers in five are not the right technique.

## Data and split

The data is MITRE ATT&CK enterprise procedure examples: sentences describing
how a named group, malware family, tool or campaign used a technique, covering
706 techniques.

The split is **by source**:

| Split | Procedures | Note |
|---|---:|---|
| Train | 14,183 | |
| Validation | 1,649 | |
| Test | 1,727 | written about 115 sources never seen in training |

At test time, every procedure ranks all 706 techniques.

## Metrics (run 40592358374; test = 1,727 procedures)

| Retriever | Recall@1 | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|---:|
| Brahmacharini v0 | 0.614 | 0.802 | 0.854 | 0.699 |
| BM25 | 0.268 | 0.478 | 0.580 | 0.372 |
| TF-IDF + logistic regression | 0.646 | 0.832 | 0.869 | 0.730 |
| Brahmacharini v0 + TF-IDF classifier, fused | 0.673 | 0.859 | 0.896 | 0.758 |
| Served design (int8, training sources only) | 0.556 | 0.735 | 0.797 | 0.638 |
| Served design + TF-IDF classifier pruned to 400 int8 weights per technique, fused | 0.650 | 0.847 | 0.887 | 0.738 |
| Hashing embedder (Smriti's previous retriever) | 0.120 | 0.226 | 0.283 | 0.177 |

### The strongest simple baseline wins

A TF-IDF model over word unigrams and bigrams, with a multinomial logistic
regression across the techniques seen in training, beats Brahmacharini on
every column: Recall@1 0.646 against 0.614, MRR 0.730 against 0.699. It was
added to the training run after the public Kaggle notebook found the same gap.
Brahmacharini is still the served retriever because it embeds passages as well
as techniques, and Sati AI's grounding needs that. The classifier only ranks
techniques it saw in training. Fused, the two do better than either alone: each score is z-scored per query and the weight (0.90 on Brahmacharini) is chosen on the validation sources. The fused model reaches Recall@1 0.673 and MRR 0.758. Serving the fusion needs the classifier exported for the API without scikit-learn, which is an open task.

### A larger encoder did not help (v1, Kaggle run 2)

Brahmacharini v1 replaced the bag of words with a transformer encoder: about
20M parameters, 4 layers, hashed words kept in order and a masked mean pool. It
was trained from scratch with InfoNCE, beside v0, on the same split and the
same test queries ([brahmacharini-transformer.md](../brahmacharini-transformer.md)).
After 200 epochs, with the best epoch by validation MRR at 190, it reaches
Recall@1 0.391 and MRR 0.470, against v0's 0.614 and 0.699. About 14,000
training procedures are too few to train an encoder of that size from nothing,
and the order it can read matters less here than the vocabulary v0 already
captures. v0 stays the served model, and v1 is kept as a negative result.

## Known limitations

- **Bag of words and bigrams.** Word order beyond adjacent pairs is lost, and
  negation is invisible: "did not use PowerShell" looks like "used PowerShell".
- **The served model is smaller, and weaker alone.** The served design (2¹⁵
  buckets, 96 dimensions, int8), trained on the training sources only and
  tested on the same split, reaches Recall@1 0.556 against v0's 0.614. Fused
  with the pruned TF-IDF classifier it reaches 0.650, so the API answers
  "which technique is this?" from the fusion. Choosing the technique whose
  mitigations to list stays with retrieval: asked "how do we defend against
  ransomware encrypting our file shares?", the fusion put Network Share
  Discovery first, where retrieval names Data Encrypted for Impact. The fusion
  was measured on behaviour descriptions, not on defence questions. The served file is trained on every source, so its own test number
  is the design's, not the file's.
- **Procedure text is MITRE's own prose.** Real alerts and analyst notes are
  terser and noisier, so recall on them will be lower than the table shows.
- **Similar techniques get confused.** Neighbouring sub-techniques (for
  example T1566.001 and T1566.002) are often ranked next to each other, and the
  wrong one can come first.

## Ethical considerations

The training data describes attacker behaviour at the level ATT&CK publishes
it. The model retrieves defensive knowledge and does not generate procedures.
Sati AI also refuses requests that look like attack tooling before retrieval
runs.
