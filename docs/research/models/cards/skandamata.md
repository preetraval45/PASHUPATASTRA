# Model card — Skandamata v0 (`sati-skandamata-v0`)

Format follows Mitchell et al. (2019). The generated table
[skandamata.md](../skandamata.md) is the source of truth. The numbers below
are a snapshot of training run 40360156287 (26 October 2026).

## Model details

- **What it does:** given a description of observed attacker behaviour, it
  ranks ATT&CK's 44 enterprise mitigations by how well each defends against
  it. Model 5 of the nine Sati models
  ([adr/Navadurga](../../../adr/Navadurga.md)): the protective response.
- **Type:** a multi-label network written from scratch in PyTorch:
  - hashed word unigrams and bigrams feed an `EmbeddingBag` (256 wide);
  - one hidden layer of 256 with dropout 0.3 follows;
  - one logit per mitigation comes out, trained with binary cross-entropy
    against the full set of right answers.

  The epoch is chosen by validation nDCG@10.
- **Built by:** an AI assistant (Claude), under the owner's direction.
- **Weights:** trained only on MITRE ATT&CK content, which MITRE licenses
  royalty-free with attribution. They are saved by the workflow but not yet
  served.

## Intended use

- **For:** proposing defensive measures for a behaviour Sati has observed. In
  Sati, a proposal is an action that Dharma must authorise (rule 2).
  Skandamata recommends; it never acts.
- **Out of scope:** deciding a response on its own. Its recommendations are
  generic ATT&CK mitigations, such as "Privileged Account Management", not
  environment-specific steps.

## Data and split

- **Behaviours:** ATT&CK procedure examples.
- **Ground truth:** ATT&CK's own `mitigates` links for each behaviour's
  technique. A sub-technique with none inherits its parent's. On average a
  behaviour has 2.8 right mitigations.
- **Split by source**, as for Brahmacharini: train 10,535, validation 1,270,
  test 1,269. The test behaviours describe 115 groups, malware families,
  tools and campaigns that never appear in training.

## Metrics (run 40578527282; test, 1,269 behaviours)

| Recommender | Hit@1 | Recall@5 | Precision@5 | MRR | nDCG@10 |
|---|---:|---:|---:|---:|---:|
| Skandamata v0 | 0.792 | 0.824 | 0.437 | 0.852 | 0.840 |
| BM25 two-hop (behaviour → techniques → their mitigations) | 0.537 | 0.646 | 0.335 | 0.659 | 0.652 |
| Popularity (the same list for everyone) | 0.232 | 0.398 | 0.206 | 0.443 | 0.433 |
| BM25 direct (behaviour → mitigation text) | 0.195 | 0.259 | 0.128 | 0.344 | 0.276 |

## Known limitations

- **The ground truth is technique-level.** A behaviour inherits every
  mitigation linked to its technique, including ones irrelevant to this
  particular procedure. Precision@5 (0.437) is capped by that as much as by
  the model.
- **Behaviour text is ATT&CK's own prose.** Real alerts are terser, so
  expect lower recall on them.
- **A small label set.** With 44 mitigations, some generic ones (Audit, User
  Training) apply widely. Popularity is reported first for that reason.
- **One unseen-source example shows where it drifts:** for compromised
  Google Workspace accounts used for C2, it recommends account controls
  (MFA, password policies), while ATT&CK lists network prevention and web
  content restriction. That is a reasonable answer, but not the labelled one.

## Ethical considerations

Defensive recommendations only. It generates no attack content, and its
training data describes behaviour at the level ATT&CK publishes it.
