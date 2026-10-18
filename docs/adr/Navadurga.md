# Navadurga — the nine Sati models

- **Status:** Accepted · 18 October 2026 (owner decision; mapping drafted by Claude)
- **Date:** 2026-10-18
- **Amends:** [SatiModels](SatiModels.md) — the model names

## Context

The owner asked for the Sati models to be named after the nine forms of Durga
worshipped across the nine days of Navratri (Navadurga), with each model doing
the work that matches its form's nature. The functional names in SatiModels
(Sati-Detect, Sati-RCA, …) described four models. The real-data programme
([RealDataModels](RealDataModels.md)) has more distinct jobs than that, and nine
fit the loop well.

CLAUDE.md allows mythology as **names only**. That is exactly what this is: a
name, followed by what the model does. There is no imagery, no devotional
language and no iconography in the UI, docs or assets.

## Decision

| # | Name | The form's nature, in one line | The model's job | Real data | Status |
|---|---|---|---|---|---|
| 1 | **Shailaputri** | the mountain's daughter — the steady foundation | Metric anomaly detection: knows what normal looks like | NAB, SMD | planned (RP-60) |
| 2 | **Brahmacharini** | discipline and study | Embeddings for Smriti recall: knowledge and memory | LogHub, incident text | planned (RP-64) |
| 3 | **Chandraghanta** | the bell that warns | Network intrusion alerting | UNSW-NB15, CIC-IDS2017 | planned (RP-61) |
| 4 | **Kushmanda** | the creator | Writes the structured hypothesis and explanation: Sati's own language model | LogHub corpus, incident text | planned (RP-65) |
| 5 | **Skandamata** | the protecting mother | Proposes the protective response. Dharma still authorises it | incident → action labels (to be sourced) | planned |
| 6 | **Katyayani** | the warrior who finds the adversary | Root-cause ranking: names the service at fault and the fault type | RCAEval | **trained** (RP-58) |
| 7 | **Kalaratri** | the night that dispels darkness | Log anomaly detection: what hides in the noise | LogHub HDFS, BGL | planned (RP-62) |
| 8 | **Mahagauri** | calm restored | Verification: confirms a system has returned to normal after an action | recovery windows (to be sourced) | planned |
| 9 | **Siddhidatri** | completion | Fusion: combines the other eight into one calibrated verdict | outputs of 1–8 | planned |

- **Naming in use:** "Katyayani (root cause)". In code, model ids are
  `sati-<name>`, e.g. `sati-katyayani-v0`. The first version trained as
  `sati-rca-v0` is Katyayani v0, and the training files keep that id until
  their next version, so published hashes stay valid.
- **"Sati" alone still means the agent**, Sati the investigation agent. These
  are the models it runs on.
- **Every model card** gives the name, the job, the data, the splits and the
  numbers, and the job comes first. A visitor who knows nothing of Navratri
  must still learn what the model does.

## Consequences

**Enables:** a model family with a memorable, coherent identity that the owner
chose, whose roles cover the loop: observe (1, 3, 7), remember (2),
understand (6), explain (4), act (5), verify (8), decide (9).

**Rules out:** any devotional or decorative treatment, including images,
mantras and festival styling. The names carry the reference; the work carries
the product.

**Revisit when:** a job outgrows one model, or two jobs merge. The mapping
changes in a new ADR, never silently.
