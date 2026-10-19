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

## Metrics (snapshot, run 39181027757; test = 1,727 procedures)

| Retriever | Recall@1 | Recall@5 | Recall@10 | MRR |
|---|---:|---:|---:|---:|
| Brahmacharini v0 | 0.609 | 0.790 | 0.845 | 0.691 |
| BM25 | 0.270 | 0.481 | 0.577 | 0.373 |
| Hashing embedder (Smriti's previous retriever) | 0.112 | 0.212 | 0.269 | 0.168 |

## Known limitations

- **Bag of words and bigrams.** Word order beyond adjacent pairs is lost, and
  negation is invisible: "did not use PowerShell" looks like "used PowerShell".
- **Vocabulary is hashed, not learned.** Collisions are rare at 2¹⁸ buckets but
  more frequent in the 2¹⁵-bucket served model. That model has not been
  separately evaluated on the test split. Doing so is an open task.
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
