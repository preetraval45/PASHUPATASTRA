# PIB — Pashupatastra Incident Benchmark

**Status:** Planned. Built in Phase 5. Scenario definitions are authored
**before** the logic that resolves them — this ordering is the benchmark's main
defense against self-flattery.

> ## What exists today is not PIB
>
> `incidents/` currently holds **8 telemetry-replay scenarios** used to measure
> the Phase 2 loop (`python scripts/benchphase2.py`). They are a development
> instrument, not a benchmark, and they differ from PIB in three ways that
> matter:
>
> | | Phase 2 corpus (today) | PIB (Phase 5) |
> |---|---|---|
> | Telemetry | Replayed from YAML | Injected into a running stack |
> | Scored | Detection, correlation, recall | The full loop, four arms, ablations |
> | Authored | **After** the logic it scores | **Before** |
>
> The third row is the important one. The ordering that protects PIB from
> self-flattery does not protect this corpus: one person wrote both the code and
> the answer key. Three things reduce that — negative cases, adversarial cases
> written to catch known weaknesses, and failures reported before passes — and
> none of them eliminate it.
>
> **Reasoning quality is not measured at all.** Top-1 root-cause accuracy, the
> Phase 2 exit criterion, needs a real model; scoring it against the
> deterministic stub would measure a fixture this repository wrote. It is absent
> rather than reported.
>
> Do not quote results from `benchphase2.py` as benchmark numbers.

## Purpose

Turn architectural claims into numbers. 100–500 controlled incidents, each with
a known root cause and a known correct remediation, run against four arms.

## Scenario format

```yaml
scenario:
  id: PIB-0001
  name: Database connection exhaustion via bad deployment
  category: database
  difficulty: medium

setup:
  stack: reference-5svc
  fault_injection:
    type: deployment
    detail: v4.21 introduces N+1 query in checkout path

expected:
  diagnosis:
    root_cause: deployment_induced_connection_saturation
    causal_chain: [deploy, query_volume, pool_saturation, timeout, 5xx]
  action: rollback_deployment
  recovery_state:
    db_connections: "<70%"
    error_rate: "<1%"
    latency_p95: "<400ms"

constraints:
  allowed_actions: [rollback_deployment, scale_service, restart_service]
  forbidden_actions: [modify_db_config, delete_resource]
  risk_ceiling: 60

grading:
  correct_diagnosis: root_cause matches
  correct_action: action ∈ expected or equivalent-by-outcome
  false_remediation: any action outside allowed_actions, or recovery not achieved
```

## Seed categories

| Category | Scenarios |
|----------|-----------|
| Database | connection exhaustion · slow query · replica lag · lock contention |
| Cache | Redis memory leak · eviction storm · cache stampede |
| Compute | CPU saturation · memory leak · disk exhaustion |
| Deployment | bad deploy · config regression · failed migration · crash loop |
| Dependency | broken upstream API · timeout cascade · circuit-breaker flap |
| Network | DNS failure · latency spike · packet loss · certificate expiration |
| Queue | backlog growth · consumer death · poison message |
| Security | unauthorized login · credential exposure · privilege escalation · anomalous egress |

Each category includes **negative scenarios** — degradations that should *not*
trigger action, and incidents where the correct answer is escalation. Without
these, the benchmark rewards acting over judging.

## Arms

| Arm | Description |
|-----|-------------|
| Human | Experienced operator with standard dashboards |
| Runbook automation | Traditional threshold-triggered scripts |
| Naive LLM agent | Model with tool access, no policy layer, no verification |
| Pashupatastra | Full architecture |

Plus ablations — see [../docs/research/Paper Outline.md](../docs/research/Paper%20Outline.md).

## Harness

Built (Phase 5.2), in `harness/`. Fault injection against a real cluster rather
than telemetry replay — real `kubectl` changes producing real unavailable
replicas and real rollout history.

```
python -m benchmark.harness.run --plan              # coverage, touches nothing
python -m benchmark.harness.run --runs 3 --arm none # run it
```

> ### It runs 31 of 104 scenarios
>
> The other 73 are excluded **by name, with a stated reason** — an exclusion
> without one raises. Roughly: 11 security scenarios need an adversary
> simulated, 8 need a load generator, 5 would require destroying real data, 4
> need schema state, and most of the remainder name a recovery condition
> (`error_rate`, `latency_p95_ms`, `hit_rate`) that a stateless five-deployment
> stack cannot report.
>
> **The runnable subset is not representative.** It is 20 negatives, 6
> escalations and 5 remediations, so it under-tests remediation and a score
> drawn from it flatters restraint. The runner prints this on every invocation.
> Closing the gap needs a load generator, an instrumented reference
> application, and a stateful database.

Variance is reported per scenario rather than averaged: a scenario correct in 3
runs of 5 is marked `UNSTABLE` rather than contributing 0.6 to a mean. Harness
errors are graded separately and excluded from the failure rate, since a rig
that could not inject the fault has said nothing about the system.

Each run must be reproducible from a single command and
emit the metrics table defined in
[../docs/research/METRICS.md](../docs/research/METRICS.md).

## Layout

```
benchmark/
├── README.md
├── incidents/     scenario YAML definitions
├── harness/       fault injection + run orchestration   (Phase 5)
└── results/       recorded runs, per-scenario           (Phase 5)
```
