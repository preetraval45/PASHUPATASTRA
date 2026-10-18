# Real-data models — Sati models built here, trained and tested on real data

- **Status:** Accepted · 18 October 2026 (owner decisions; drafted by Claude)
- **Date:** 2026-10-18
- **Phase:** Research plan, Block C (brought forward)
- **Amends:** [SatiModels](SatiModels.md) on who builds the models, and
  [ExternalBenchmark](ExternalBenchmark.md) on RCAEval being test-only.

## Context

On 18 October 2026 the owner set three requirements:

1. **All of the AI is the project's own.** Sati runs on Sati models. General
   LLMs remain only as the baseline to beat and as a labelled backup until
   Sati-LM can answer by itself.
2. **Claude builds and trains the models** — data pipelines, model code,
   training and evaluation. This reverses the earlier rule that model code was
   the owner's alone (RESEARCH PLAN.md, *How to use this plan*).
3. **Trained and tested on real-life data**, not only on the Kaal generator.

And one standing constraint: **nothing runs on the owner's machine** and only
free services are used.

## Decision

### The models and their real data

| Model | Job | Real training / test data | Licence of the data |
|---|---|---|---|
| **Sati-RCA** | Rank the root-cause service of an incident, and name the fault type | **RCAEval** RE1 + RE2 — 645 real fault-injection cases on Online Boutique, Sock Shop, Train Ticket | MIT (Hugging Face copy) |
| **Sati-Detect (metrics)** | Anomaly scoring on metric series | **NAB** and **SMD** — real server and application metrics with labelled anomalies | MIT (both) |
| **Sati-Detect (network)** | Flag intrusion traffic | **UNSW-NB15** and **CIC-IDS2017** — real captured traffic with labelled attacks | research use; UNSW-NB15 commercial use by the authors' agreement |
| **Sati-Detect (logs)** | Flag anomalous log sequences | **LogHub** HDFS and BGL — real system logs with anomaly labels | research use with citation (LogPAI) |
| **Sati-Embed** | Incident text → vectors for Smriti | LogHub + incident narratives from the above | as above |
| **Sati-LM** *(later)* | Write the structured hypothesis | LogHub corpus + the above | as above |

Each dataset gets a datasheet before training ([datasheets.md](../research/datasheets.md):
source, licence, size, labels, known flaws). A dataset whose licence forbids publishing derived weights is
used for evaluation only.

### Splits that test diagnosis, not memory

- **Sati-RCA: leave-one-system-out.** Train on two of the three systems, test on
  the third, rotating. A model tested on a system it trained on has learned the
  system, not diagnosis. Also reported: held-out *fault type*, and an
  in-distribution split by repetition, so the generalisation gap is visible.
- **Sati-Detect: time-ordered.** Train on the earlier part of each series or
  capture, test on the later; for UNSW-NB15, the dataset's own train/test files.
  Normalisation is fitted on training data only.
- **Test-only, forever:** PIB, the 20 labelled incidents, and whichever external
  benchmark replaces RCAEval in that role. RCAEval is now training data, so the
  zero-shot external result (RP-33) moves to a benchmark not used for training.

### Where it runs

| Step | Where | Why |
|---|---|---|
| Download, features, gradient boosting, evaluation | **GitHub Actions** (public repo: free; 4 CPU, 16 GB) | Tabular models train in minutes on CPU |
| Neural models (autoencoder, GNN, encoder, Sati-LM) | **Kaggle** notebooks (free GPU quota) | No free GPU anywhere else |
| Serving | The **API Lambda**, CPU | Sati-RCA v0 is a tree ensemble; inference is milliseconds |

Results are generated files committed by the workflow; trained weights are kept
as workflow artifacts and published as GitHub release assets once evaluated
(the owner chose public weights, Apache-2.0 — [SatiModels](SatiModels.md)).

### The rules still hold

- Every Sati-RCA answer names the metric series and time window behind each
  feature it used, so its hypothesis carries citations by construction (rule 1).
- Served through the AI Gateway as a provider; outputs are validated schemas
  (rules 4, 5). Sati proposes, Dharma authorises (rule 2).
- `packages/core` stays free of ML libraries; models live in `packages/sati`.

### Disclosure

The paper and every model card state that the models were designed, written and
trained by an AI assistant (Claude) under the owner's direction, with the owner's
decisions recorded here.

## Consequences

**Enables:** models trained and measured on real failures and real attacks, with
the generalisation gap reported; a site whose AI is the project's own.

**Rules out:** tuning on any test split; publishing a number without its split;
calling a model "better" without the LLM baseline on the same split.

**Revisit when:** a dataset's licence turns out not to allow weight release, or
Sati-RCA fails to beat a simple statistical ranker on held-out systems (then the
paper says so).

## Alternatives considered

- **Train only on the Kaal generator.** Rejected by the owner: real data first.
- **Fine-tune an open LLM instead.** Not the project's own model, and it moves
  the contribution away from a purpose-built diagnostic model.
- **Train on the owner's PC.** Ruled out: nothing runs locally.
