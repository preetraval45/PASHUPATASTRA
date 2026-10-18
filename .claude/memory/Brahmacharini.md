# Brahmacharini

- **Date:** 2026-10-18
- **Phase:** Block H — RP-64
- **Commit(s):** this push

## What changed

packages/sati/sati/embed/ holds data.py (ATT&CK `uses` relationships with a
description, from intrusion sets, malware, tools and campaigns to techniques;
split 80/10/10 by source), model.py (hashed-ngram EmbeddingBag dual encoder,
InfoNCE), metrics.py (torch-free ranks, summarise and BM25), run.py and
report.py. A `brahmacharini` job in train-sati.yml installs CPU torch. The
Models page has a section for it.

## Decisions made

- The task is behaviour → technique retrieval, because ATT&CK provides real
  labelled pairs under a permissive licence. The old plan used LogHub, which
  is research-only.
- One positive per technique per batch, so no in-batch negative is secretly
  a positive.

## Gotcha

- Never run `ruff --fix` locally on packages/sati. The local ruff (0.16)
  strips `noqa` comments that CI's ruff (<0.13) needs, notably E402 and E731.
