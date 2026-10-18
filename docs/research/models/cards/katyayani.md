# Model card — Katyayani v0 (`sati-rca-v0`)

Format follows Mitchell et al., *Model Cards for Model Reporting* (FAT* 2019).
The numbers below are a snapshot. The live, generated table is
[sati-rca.md](../sati-rca.md), and it is the source of truth.

## Model details

- **What it does:** ranks the services in a microservice system by how likely
  each is the root cause of an incident, and names the fault type.
  Model 6 of the nine Sati models ([adr/Navadurga](../../../adr/Navadurga.md)).
- **Type:** LightGBM `lambdarank` over per-service features, plus a
  multiclass head for the fault type. Parameters are fixed in
  `packages/sati/sati/rca/model.py` before any result.
- **Features:** for each service and metric family (cpu, memory, latency,
  traffic, errors, other):
  - the robust shift after the fault against that series' own pre-fault
    baseline (median and MAD), its peak, and its onset;
  - all of these log-compressed and ranked within the incident.

  Every feature records the metric series it came from.
- **Built by:** an AI assistant (Claude), under the owner's direction, in this
  repository ([adr/RealDataModels](../../../adr/RealDataModels.md)).
- **Licence:** Apache-2.0. RCAEval is MIT. Each run's artefact is identified by
  its sha256 in [sati-rca-v0.meta.json](../sati-rca-v0.meta.json).

## Intended use

- **Ranking candidate root-cause services** for an operator or for Sati, the
  investigation agent, to investigate first. Each ranking carries citations to
  the metric series behind it.
- **Out of scope:** acting on its own. Its output is a hypothesis, and any
  action still goes through Dharma (rule 2). It is also not for security
  incidents: it reads service metrics, not authentication or network events.

## Training data

RCAEval (Pham et al., WWW 2025): RE1 and RE2, 645 real fault-injection cases
on Online Boutique, Sock Shop and Train Ticket. The dataset revision is pinned
per run.

## Evaluation data and splits

| Split | What it tests |
|---|---|
| Leave one system out | a whole system never seen in training: **the claim** |
| Held-out fault type | a kind of failure never seen in training |
| Held-out repetition | in-distribution; the optimistic number |
| RE3 (90 code-level faults) | never trained on at all |

## Metrics (snapshot, run 39170294506)

| Held out | Top-1 root cause | No-learning baseline |
|---|---:|---:|
| A system never seen (n = 645) | 88.4% | 57.0% |
| A fault type never seen | 89.3% | 57.0% |
| RE3, never trained on (n = 90) | 80.0% | 48.9% |
| Never-seen system, without the series-count feature | 88.7% | — |

Fault type, end to end: about 55–58% per held-out system.

## Known limitations

- **The injection time is given**, as in RCAEval's standard setting. A
  deployed system must detect the onset itself.
- **Weakest on `loss` and `delay` faults** (about 67% and 79% top-1 when held
  out). Network faults spread across callers and blur which service moved
  first.
- **Five candidate root causes per system** in RE1 and RE2. Real estates have
  more.
- **Fault-type accuracy is modest.** Treat the fault label as a lead, not a
  finding.

## Ethical considerations

It cites what it relied on, so a wrong ranking can be checked rather than
trusted. It cannot act. A misdiagnosis costs investigation time, never an
unreviewed change.
