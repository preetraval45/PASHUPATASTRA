# Sati-Embed (Brahmacharini) — adopt for behaviour-to-technique recall

- **Status:** Accepted · 18 October 2026 (RP-64; Claude, on the generated results)
- **Evidence:** [models/brahmacharini.md](../research/models/brahmacharini.md), train-sati run 39170979376

## Context

Smriti recalls by meaning through `HashingEmbedder`, a lexical hash with no
learning, so "pool exhausted" and "no free connections" do not meet. Backlog
2.5 asked for recall to be measured, and for an embedder to be adopted only on
that evidence.

## What the measurement found

Each query is a real ATT&CK procedure example, written about one of 115
groups, malware families, tools or campaigns never seen in training. Each
query ranks all 706 techniques.

| Retriever | Recall@1 | Recall@10 | MRR |
|---|---:|---:|---:|
| **Brahmacharini v0** | **0.609** | **0.845** | **0.691** |
| BM25 | 0.270 | 0.577 | 0.373 |
| HashingEmbedder | 0.112 | 0.269 | 0.168 |

## Decision

- **Adopted for mapping behaviour to ATT&CK techniques.** It is more than
  twice as good as BM25 at top-1 and five times better than the current
  embedder, on attackers it never saw.
- **For incident-to-incident recall in Smriti, not yet adopted.** The test
  above is behaviour → technique. Incident → past incident is a related but
  different task, so Brahmacharini replaces `HashingEmbedder` there only after
  a measurement on incident pairs. Until then the hashing embedder stays, and
  its weakness stays documented.

## Consequences

**Enables:** citing the technique an observed behaviour most resembles, with
the ranked alternatives shown.

**Rules out:** treating the top match as a finding. It is a recall, and a
human or the evidence confirms it.
