# External benchmark — a result on data this repository did not write

- **Status:** Accepted · 18 October 2026 (feasibility by Claude; the choice is the owner's)
- **Date:** 2026-10-10
- **Phase:** Research plan, Block D

## Context

Every number in the paper so far comes from PIB and the labelled incidents,
both written here. That is the first threat to validity in §9, and the only
answer that does not need a second author is a result on a benchmark someone
else built. RP-31 picks one; RP-32 adapts it; RP-33 runs Sati-RCA on it
zero-shot (no training or tuning on it).

Constraints that shape the choice:

- **Inputs must match Sati-RCA's:** per-service metrics, events and a service
  dependency graph, with the root-cause *service* and fault type as the label.
- **Free compute only, nothing on the owner's PC:** GitHub Actions runners,
  Kaggle, or the Oracle Always Free box (4 ARM cores, 24 GB).
- **Licence must allow** using the data and publishing results.
- **Zero-shot and test-only:** the benchmark joins the contamination guard
  (RP-18), so Kaal must not reproduce its topologies.

## Feasibility (checked 10 October 2026)

Sources: each project's GitHub repository and README, the GitHub API (licence),
Hugging Face and Zenodo (data licence).

| | **RCAEval** | **OpenRCA** | **AIOpsLab** | **ITBench** |
|---|---|---|---|---|
| Venue | WWW'25, ASE'24, FSE'26 | ICLR'25 | Microsoft, 2025 | ICML'25 |
| Repo | phamquiluan/RCAEval | microsoft/OpenRCA | microsoft/AIOpsLab | itbench-hub/ITBench |
| Code licence | MIT | MIT | MIT | Apache-2.0 |
| Data licence | MIT (Hugging Face), CC-BY-4.0 (Zenodo) | **not stated** — data on Google Drive | n/a — generated live | n/a — generated live |
| Form | **Offline dataset** | Offline dataset | Live: deploys apps on Kubernetes, injects faults, agent interacts | Live: Kubernetes scenarios, agent interacts |
| Size | 735 failure cases, 9 datasets; 3.4 GB Parquet, downloadable one suite or case at a time | Three systems (Telecom, Bank, Market); README asks for ≥ 80 GB disk, 32 GB RAM | Problem registry across several apps | 6 open SRE scenarios (+ CISO, FinOps); more via hosted platform |
| Systems | Online Boutique, Sock Shop, Train Ticket | Telecom, Bank, Market | Hotel Reservation, Social Network, others | Kubernetes microservice apps |
| Telemetry | Metrics (all); logs and traces (RE2, RE3) | Metrics, traces, logs | Metrics, traces, logs, live `kubectl` | Live cluster |
| Label | **Root-cause service** + root-cause indicator; fault type | Natural-language query → time, component, reason | Per-task: detection, localisation, analysis, mitigation | Per-scenario success |
| Fault types | cpu, mem, disk, delay, loss, socket; code-level f1–f5 (RE3) | Per system | Misconfig, app and infra faults | SRE incident mechanisms |
| Runs on free compute | **Yes.** One suite fits a GitHub Actions runner (16 GB RAM); readme recommends 16 GB, 8 cores | **Doubtful.** 80 GB / 32 GB exceeds runners; Oracle box has 24 GB RAM | **Possibly.** kind on a GitHub runner, like PIB — but the apps are heavier than PIB's | **Possibly** for the 6 open scenarios; the hosted platform needs registration |
| Fit to Sati-RCA | **Direct:** metrics + service label, published RCA baselines (e.g. BARO) on the same data | Partial: built for LLMs reading raw telemetry; label is free text elements | Partial: an agent loop, not a diagnosis dataset | Partial: end-to-end agent tasks; n is small |

### Notes per candidate

- **RCAEval** is the closest match. Its label is the root-cause service, which is
  exactly what RCA@1 and RCA@3 score, and it ships reproducible baselines, so
  RP-33 can compare against published numbers on the same cases. **Gap:** RE1
  has metrics only. The service dependency graph has to come from the three
  apps' public manifests, or from traces where RE2 and RE3 have them. The
  adapter (RP-32) must record where each graph came from.
- **OpenRCA** is the most-cited LLM benchmark, so it is the strongest
  comparison against LLMs. But its data licence is not stated, its hardware
  ask exceeds every free option, and its task is phrased for an LLM. Mapping
  that to a ranked-service answer would change the task.
- **AIOpsLab** tests the whole loop (detect → localise → mitigate), which suits
  the *architecture* claim better than the *model* claim. It is a candidate for
  later, as an end-to-end arm next to PIB, not as RP-33.
- **ITBench** has the most realistic SRE scenarios, but only 6 are open. That
  n is too small for intervals, and the rest sit behind a hosted platform.

### Contamination

RCAEval's fault types (cpu, mem, disk, delay, loss) overlap the families Kaal
will generate. That is fine: generating the same *kinds* of fault is expected.
Reproducing RCAEval's *topologies* or event sequences is not. RP-18's guard
hashes the Online Boutique, Sock Shop and Train Ticket graphs, and fails if Kaal
samples them.

## Decision

*(Owner — RP-31.)* **Claude recommends RCAEval**, starting with RE2 (metrics,
logs and traces; 270 cases, six fault types), then RE1 for n. Its labels are the
ones Sati-RCA predicts, it runs on free runners, its data licence is explicit,
and it has published baselines to compare against.

**Decision (owner, 18 October 2026): RCAEval**, starting with RE2. It is test-only and zero-shot, and its three topologies join the RP-18 contamination guard. The owner's reading of the four papers is still to be logged in [related-work.md](../research/related-work.md).

## Consequences

**Enables:**
- A §7 result on data this repository did not author, against baselines it did
  not write.
- RCA@k with intervals at n in the hundreds, not 20.

**Rules out:**
- Training or tuning anything on the chosen benchmark. It is test-only and joins
  the contamination guard.
- Changing the subset after the first run. RP-32 commits it first.

**Revisit when:**
- Sati-RCA's inputs change (for example, if it starts reading logs), so another
  benchmark fits better.
- OpenRCA publishes a data licence, and a free machine with 32 GB of memory
  becomes available.

## Alternatives considered

The other three candidates are above. Running *all four* was also considered,
and rejected for Block D: each one needs its own adapter and pre-declared
subset, and the plan has two weeks for this.
