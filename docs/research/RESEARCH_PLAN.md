# Research & Learning Plan

**16 weeks · Monday 12 October 2026 → Sunday 31 January 2027**

One plan for three things that are the same work: learning AI/ML properly,
closing the gaps the paper admits to in §9, and finishing the platform work
those gaps depend on. Every task either teaches something an experiment needs,
produces evidence the paper needs, or both. Learning that no experiment needs
is deferred.

This plan feeds [ROADMAP.md](../ROADMAP.md) and does not replace it. When a task
here closes a roadmap item, tick the roadmap in the same change.

---

## How to use this plan

**Every task has an ID (`RP-01` … `RP-31`) and an owner.**

| Owner | Meaning |
|---|---|
| **Claude** | Ask in Claude Code: *"Do RP-06."* This file is the spec; Claude reads the task, does it, runs the tests, and reports against the *Done when* line. Your time is the review, listed separately. |
| **You** | Learning, reading, judgement calls and decisions. These cannot be delegated without defeating their purpose — the learning is yours, and so is authorship of the paper. |
| **Both** | Claude drafts or builds; you review, decide, or rewrite in your own voice. The task says which half is which. |

**Rules**

1. **A task is done when its *Done when* line is true**, not when work stops.
   Tick it here: `- [x]`. Partial: `- [~]` with what remains.
2. **Dependencies are hard.** A task does not start before what it depends on
   is done.
3. **Pre-declare before running.** Subsets, metrics and answer keys are
   committed *before* the results exist — the commit order is the evidence.
4. **Slip a week, don't skip a block.** Block B (diagnosis) is the one that must
   not be cut.
5. **The paper is yours.** Claude drafts prose on request; you rewrite it in your
   own voice and check every claim against the generated tables. Disclose AI
   assistance as the target venue's policy requires.

**Capacity assumed: ~12.5 h/week of your time** — Mon–Fri 1.5 h, Sat 3 h,
Sun 2 h. Claude's build tasks cost you only review time. Long model runs happen
overnight on your machine (it must be left on with the kind cluster up). If your
hours differ, say so and the calendar gets re-flowed. The calendar also shows
light weeks for Thanksgiving (26 Nov) and the holidays.

---

## Where things stand (9 October 2026)

| Area | State |
|---|---|
| Engineering discipline | Structured outputs, AI Gateway, generated tables, failure-first reporting, Wilson intervals — ahead of any beginner curriculum |
| PIB | 104 scenarios; 31 executable (20 negative, 6 escalation, 5 remediate) |
| Arms | `runbook`, `pashupatastra` have data; `naive-llm` gated off ([arms.py](../../benchmark/harness/arms.py)); `human` blocked on operators |
| Ablations | `no-policy`, `no-verification` implemented, **n = 0** in [tables.md](tables.md) — never run |
| Diagnosis (RCA) | Apparatus exists ([diagnosis.py](../../packages/core/pashupatastra/diagnosis.py)); **never measured** with a real model. Phase 2 exit criterion not met |
| Injection study | 3 local models × 90 turns, recorded ([experiments/](experiments/README.md)) |
| Detection | 4 statistical strategies + harness ([benchdetect.py](../../scripts/benchdetect.py)); ML detector open |
| Smriti | Lexical `HashingEmbedder`; real embedder open |
| Paper | §1, §3–§6, §9 written; §2, §7 prose, §8, §10 missing |
| Hardware | RTX 5070 Ti 16 GB + Ollama — 7–8B models, not 70B |

**The three gaps that matter most**

1. The paper argues against "just let the LLM decide" with **no LLM in the
   loop** — `naive-llm` has no data.
2. **Diagnosis quality is unmeasured** — nothing says whether Sati reasons well.
3. **The benchmark is self-authored** — the fix that needs no second author is a
   result on a benchmark someone else built.

**One design correction.** Adding an LLM only to `naive-llm` would change two
variables at once (proposer *and* policy layer). The clean design is 2 × 2:

| | No policy, no verification | Dharma + verification |
|---|---|---|
| **Deterministic proposer** | `runbook` *(have)* | `pashupatastra` *(have)* |
| **LLM proposer** | `naive-llm` *(RP-06)* | `pashupatastra-llm` *(RP-06)* |

Rows isolate the proposer; columns isolate the architecture.

---

## Timeline

| Block | Weeks | Dates | Tasks | Exit |
|---|---|---|---|---|
| A · LLM foundations + LLM arms | 1–5 | Oct 12 – Nov 15 | RP-01 – RP-10 | 2 × 2 arms table with data, N = 3, 3 models |
| B · Diagnosis | 6–10 | Nov 16 – Dec 20 | RP-11 – RP-18 | RCA@1/@3 with intervals; §7, §8 drafted |
| — · Buffer | 11 | Dec 21 – Dec 27 | — | Catch-up only |
| C · External validity | 12–13 | Dec 28 – Jan 10 | RP-19 – RP-21 | One table from data this repo did not write |
| D · ML + deep learning | 13–15 | Jan 4 – Jan 24 | RP-22 – RP-27 | ML-detector ADR; embedder decision |
| E · Paper completion | 15–16 | Jan 18 – Jan 31 | RP-28 – RP-31 | Full draft, reproducibility, venue decision |

Blocks C and D overlap in week 13, which is intended: C is mostly Claude plus
overnight runs, while D starts with your reading.

**Critical path:** RP-05 → RP-06 → RP-08 → RP-10 and RP-12 → RP-13 → RP-14 →
RP-17 → RP-18. A slip on either chain moves the end date. Everything else has
float.

**Checkpoints**

- **Sun 8 Nov** — the LLM arms have run records. If not, Block C shrinks to the
  feasibility report only (RP-19); Block B keeps its full time.
- **Sun 20 Dec** — §7 and §8 drafted. If not, the buffer week absorbs it.
- **Sun 17 Jan** — the ML decision is recorded. If not, it becomes a §9
  limitation rather than a result. The paper does not wait for it.

---

## Tasks

Each task gives: **Owner · Effort · Depends · Closes** (roadmap item), then
*Why*, *Steps*, *Done when*.

### Block A — LLM foundations and the LLM arms

- [ ] **RP-01 · Run the two unrun ablations**
  **Claude** · 1 session + overnight · your review 20 min · Depends: kind cluster up · Closes: ROADMAP 5.4 run evidence
  *Why:* `no-policy` and `no-verification` are implemented, but Table 2 shows
  n = 0. These are free results that need no model.
  *Steps:*
  1. Confirm the cluster: `kubectl get nodes`. If it is down, stop and say so; do not substitute.
  2. `python -m benchmark.harness.run --runs 3 --arm pashupatastra --ablation no-policy`, then `--ablation no-verification`.
  3. `python scripts/papertables.py` → regenerate [tables.md](tables.md).
  4. Report FRR/HIR/ARR deltas against the full architecture, plus any scenario flagged `UNSTABLE`.
  *Done when:* Table 2 has n > 0 for both rows, and the run records exist under `benchmark/results/`.

- [ ] **RP-02 · Learn: how a transformer works**
  **You** · 5 h · Depends: —
  *Why:* every LLM result in this paper is shaped by tokens, context and
  sampling, and you need to be able to explain them.
  *Steps:*
  1. Karpathy, *Neural Networks: Zero to Hero* — "Let's build GPT: from scratch". **Code along** in a scratch notebook outside the repo.
  2. Jay Alammar, *The Illustrated Transformer*.
  3. Vaswani et al. 2017, *Attention Is All You Need* — §3 only.
  *Done when:* without notes, you can explain tokens → embeddings → attention (Q, K, V) → next-token distribution, and why context is finite. Write it as a one-page note in your own words.

- [ ] **RP-03 · Related-work log: scaffold and first four papers**
  **Both** · Claude 1 session; You 4 h reading · Depends: —
  *Steps:*
  1. **Claude** creates `docs/research/related-work.md`. Each entry has fields: citation, research question, dataset, baselines, metrics, what it does *not* claim, how PIB / Pashupatastra differs, *my takeaway* (left blank). Claude pre-fills the citations only — no summaries in your name.
  2. **You** read and fill: Ahmed et al. ICSE 2023 (LLM root-cause and mitigation for cloud incidents); Chen et al. EuroSys 2024 (RCACopilot); Yao et al. 2022 (ReAct); Greshake et al. 2023 (indirect prompt injection).
  *Done when:* four entries are complete, with the takeaway in your words.

- [ ] **RP-04 · Learn: sampling, non-determinism, tool calling**
  **You** · 4 h · Depends: RP-02
  *Steps:*
  1. Hugging Face LLM Course — the generation / inference chapters (temperature, top-p, greedy vs sampling).
  2. Structured output and tool calling: how a model is held to a schema and how it fails (refusal, truncation, invalid JSON). Then read [gateway.py](../../packages/core/pashupatastra/gateway.py) and the provider in `services/api/app/engines/providers/openaicompat.py` and map each failure to where the code handles it.
  3. Ollama's OpenAI-compatible API docs.
  *Done when:* you can say why temperature 0 is still not fully deterministic on a GPU, and which Gateway error type each failure mode becomes.

- [ ] **RP-05 · ADR: the LLM arms (2 × 2 design)**
  **Both** · Claude 1 session; You 1 h review + decisions · Depends: RP-04 · Closes: design half of ROADMAP 5.3 `naive-llm`
  *Steps:*
  1. **Claude** drafts `docs/adr/LLMArms.md`, covering:
     - the 2 × 2 above and what each cell isolates;
     - both LLM arms get the identical `Brief` and identical prompt, and only the gate differs;
     - the proposer goes through the AI Gateway and returns a validated schema (rules 4 and 5), with no SDK import in core;
     - temperature and seed recorded per run;
     - LLM *errors* (invalid schema, timeout, refusal) graded separately from *wrong answers*, the way harness errors already are;
     - the stub still refuses.
  2. **You** decide and record: the models (default `qwen2.5:7b`, `mistral` 7B, `llama3` 8B), the temperature (default 0.2), and whether a hosted model (Bedrock) is added for one comparison row, which costs money.
  *Done when:* the ADR is committed with your decisions in it.

- [ ] **RP-06 · Build the LLM proposer and both LLM arms**
  **Claude** · 1–2 sessions · your review 1 h · Depends: RP-05
  *Steps:*
  1. Add an LLM proposer behind the Gateway: input is a `Brief`, output is a validated proposal schema with a choice restricted to `allowed_actions` or "do nothing" or "escalate", plus a rationale.
  2. `NaiveLLMArm`: replace the second `ArmUnavailable` with the proposer, executing without Dharma or verification. Keep the first refusal when no model is configured.
  3. Add `PashupatastraLLMArm`: the LLM proposer → Dharma → `Remediator` → verification, the same path `pashupatastra` uses. Register it in `run.py` `ARM_NAMES`.
  4. Tests in `benchmark/harness/testarms.py`:
     - both arms refuse on the stub;
     - neither can see `expected.action` (extend the redaction test);
     - a schema-invalid response is graded as an error, never as a decision;
     - a proposal outside `allowed_actions` is rejected.
  5. Run the full test suites and confirm no SDK import has entered core (the CI gate).
  *Done when:* all tests pass, and the CI gate passes.

- [ ] **RP-07 · Smoke run on a real model**
  **Both** · You 30 min; Claude 1 session · Depends: RP-06
  *Steps:*
  1. **You**: `ollama pull qwen2.5:7b mistral llama3`, and confirm `ollama list`.
  2. **Claude**: run 3 scenarios (one negative, one escalation, one remediate) × both LLM arms × `qwen2.5:7b`, N = 1. Inspect every record by hand for leaked answers, parse errors and nonsense rationales. Fix before scaling.
  *Done when:* six clean run records, and any problem found is fixed with a test.

- [ ] **RP-08 · Full arms run**
  **Claude** · 1 session + 2–3 overnights · your review 1 h · Depends: RP-07
  *Steps:*
  1. Pre-declare the run matrix in a committed file *before* running: 31 scenarios × {`naive-llm`, `pashupatastra-llm`} × 3 models × N = 3 = 558 runs. Deterministic arms are re-run at N = 3 if their records are stale.
  2. Batch overnight, resuming from where it stopped (skip scenario/arm/model/run combinations that already have a record).
  3. Extend `scripts/papertables.py`: one row per (arm, model); the stability flag per scenario; LLM-error counts shown beside accuracy.
  *Done when:* Table 1 shows all four arms × 3 models with n reported, and is generated rather than hand-written.

- [ ] **RP-09 · Significance between arms**
  **Both** · You 3 h reading; Claude 1 session · Depends: RP-08
  *Steps:*
  1. **You** read Dror et al. ACL 2018, *The Hitchhiker's Guide to Testing Statistical Significance in NLP* — paired tests and bootstrap.
  2. **Claude** adds paired comparisons to `papertables.py` (McNemar on per-scenario correctness and a paired bootstrap CI on FRR), for the row pair and the column pair of the 2 × 2.
  *Done when:* the table states which differences survive and which do not, with n.

- [ ] **RP-10 · §7 Evaluation — arms**
  **Both** · Claude draft 1 session; You 3 h rewrite · Depends: RP-09
  *Steps:* Claude drafts from the generated tables only: what each cell of the 2 × 2 shows, with the 31-scenario restraint bias stated *beside* the numbers. You rewrite it in your voice and check every sentence against the table.
  *Done when:* §7 has an arms subsection with no number that is not in [tables.md](tables.md).

### Block B — Diagnosis

- [ ] **RP-11 · Learn: evaluating LLM systems**
  **You** · 5 h · Depends: RP-04
  *Steps:* Liang et al. 2022, *HELM* (the framing); Hamel Husain's posts on LLM evals (error analysis first, and validating any LLM-as-judge); a short read on benchmark contamination. Add 3 entries to the related-work log.
  *Done when:* you can say why a 7B model might "know" a public incident write-up, and how this study guards against it.

- [ ] **RP-12 · Grow the labelled corpus from 8 to 20 incidents**
  **Both** · You 6 h; Claude 1–2 sessions · Depends: — (start in week 6) · Closes: part of ROADMAP 2.6
  *Why:* the Phase 2 exit criterion needs 20, and the answer key's independence is the whole value of the set.
  *Steps:*
  1. **You** write the 12 new incident specs: what broke, the true root cause, the correct action, and red herrings. Keep the proportion of negatives and escalations. You write these, not Claude: an answer key written by the same assistant that builds the reasoning is a weaker control.
  2. **You commit the answer keys alone first.**
  3. **Claude** builds the telemetry fixtures in `benchmark/incidents/` to match your specs, and runs the strict loader and `scripts/benchphase2.py`.
  *Done when:* 20 scenarios validate, and git history shows the answer-key commit before any diagnosis run.

- [ ] **RP-13 · Diagnosis benchmark script**
  **Claude** · 1 session · your review 45 min · Depends: RP-06 (proposer and Gateway wiring)
  *Steps:* `scripts/benchdiagnosis.py` runs Buddhi through the Gateway over the labelled corpus, per model, N runs. It reports through the existing `diagnosis.py` functions: RCA@1, RCA@3, precision-when-answering, grounding, abstention rate, and Wilson intervals, plus suppressed-hypothesis counts and citation validity. It refuses on the stub, and writes JSONL records that a table generator reads.
  *Done when:* tests pass, and a stub run refuses with a clear message.

- [ ] **RP-14 · Run diagnosis; decide the Phase 2 criterion**
  **Both** · Claude 1 session + 1 overnight; You 1 h · Depends: RP-12, RP-13
  *Steps:* **Claude** runs 20 incidents × 3 models × N = 3 and generates the table. **You** write the Phase 2 exit verdict in ROADMAP §2.6 — met, not met, or met for some models — in one paragraph.
  *Done when:* the table exists, and ROADMAP §2.6 states the verdict.

- [ ] **RP-15 · Calibration and temperature**
  **Both** · You 2 h reading; Claude 1 session · Depends: RP-14
  *Why:* hypothesis confidence feeds Dharma's effective risk, so miscalibration is a safety problem, not a statistic.
  *Steps:* **You** read a reliability-diagram / expected-calibration-error tutorial. **Claude** adds a reliability diagram and ECE per model, and a temperature 0 vs 0.7 comparison on a pre-declared 8-incident subset.
  *Done when:* a figure and a table are generated, and one paragraph says whether confidence can be trusted as a risk input.

- [ ] **RP-16 · §7 Evaluation — diagnosis**
  **Both** · Claude draft; You 3 h · Depends: RP-15
  *Done when:* the diagnosis subsection exists, and every number traces to a generated table.

- [ ] **RP-17 · Failure categorisation**
  **Both** · Claude 1 session; You 4 h judging · Depends: RP-14, RP-08
  *Steps:* **Claude** extracts every wrong diagnosis and every escalation into a review sheet and proposes categories: missing telemetry, red herring followed, right cause / wrong action, fabricated citation caught, policy ceiling, LLM error. **You** assign each case a category; that judgement is yours. Claude then counts and tabulates.
  *Done when:* every failure has a category assigned by you, and the counts table is generated.

- [ ] **RP-18 · §8 Failure analysis**
  **Both** · You 4 h writing · Depends: RP-17 · Closes: ROADMAP 6.1 failure analysis
  *Steps:* read the failure-analysis sections of OpenRCA and AIOpsLab for structure. Then answer the outline's question — what the escalation cases share — from the counts.
  *Done when:* §8 is drafted, and ROADMAP 6.1 is ticked.

### Block C — External validity

- [ ] **RP-19 · Choose an external benchmark**
  **Both** · You 4 h reading; Claude 1 session · Depends: —
  *Steps:*
  1. **You** read OpenRCA (Xu et al., ICLR 2025), RCAEval (Pham et al., 2025), AIOpsLab (Chen et al., Microsoft, 2025) and ITBench (IBM, 2025).
  2. **Claude** writes a feasibility note for each: licence, data size, setup on one machine without a cloud bill, how directly its task maps onto Sati's diagnosis, and its published baselines.
  3. **You** choose, and record the reason. The likely pick is OpenRCA or RCAEval, because they are offline data with no cluster.
  *Done when:* the decision is recorded in `docs/adr/ExternalBenchmark.md`.

- [ ] **RP-20 · Adapter and a pre-declared subset**
  **Claude** · 1–2 sessions · your review 1 h · Depends: RP-19, RP-13
  *Steps:* `benchmark/external/<name>/` turns cases into Drishti events, and the label is never visible to the adapter's output (a test enforces this). Commit the chosen subset — case IDs and the rule used to choose them — before any run.
  *Done when:* the tests pass, and the subset file's commit predates any result.

- [ ] **RP-21 · External run and write-up**
  **Both** · Claude 1 session + overnight; You 3 h writing · Depends: RP-20
  *Steps:* **Claude** runs the subset × the best local model × N = 3, and compares it with the benchmark's published baselines only where they are actually comparable. **You** write the §7 subsection, and update §9's first threat to say what this does and does not repair.
  *Done when:* there is a generated table from data this repository did not author.

### Block D — Classical ML and deep learning

The rule is already set in the repository: an ML detector earns its place only
by beating the best statistical strategy on the benchmark.

- [ ] **RP-22 · Learn: classical anomaly detection, honestly**
  **You** · 5 h · Depends: —
  *Steps:* the scikit-learn MOOC (the pipelines and evaluation modules only); Liu et al. 2008, *Isolation Forest*; and **Wu & Keogh 2021, *Current Time Series Anomaly Detection Benchmarks are Flawed*** — read it before touching NAB or Yahoo.
  *Done when:* you can say which public datasets Wu & Keogh consider trivial or mislabelled, and what that means for this study.

- [ ] **RP-23 · Public datasets and classical ML detectors**
  **Claude** · 1–2 sessions · your review 1 h · Depends: RP-22
  *Steps:*
  1. Write loaders for NAB and SMD (Su et al., KDD 2019) into `evaluation.py`'s `Series`, under an experiment directory, not core.
  2. Implement Isolation Forest and a gradient-boosted residual model as `DetectionStrategy`, with time-ordered fit/score (never shuffled).
  3. Keep scikit-learn an experiment dependency or an optional extra, so core stays light.
  4. Score them with the existing harness on precision, episode recall, lead time, and false alarms per 1000, against the 4 statistical strategies.
  *Done when:* a generated comparison table exists, with fixed seeds.

- [ ] **RP-24 · Learn: PyTorch and backpropagation**
  **You** · 5 h · Depends: RP-02
  *Steps:* the PyTorch "Learn the Basics" tutorial end to end, and 3Blue1Brown's *Neural Networks* backpropagation episodes.
  *Done when:* you have written a training loop from memory: data loader, model, loss, optimizer, train and validation.

- [ ] **RP-25 · Deep detector, written by you**
  **You**, with Claude reviewing · 6 h · Depends: RP-23, RP-24
  *Why:* this is the learning exercise, so delegating it defeats it.
  *Steps:* write a small LSTM or 1-D convolutional autoencoder that uses reconstruction error as the anomaly score, trained on the GPU and wrapped as a `DetectionStrategy` so the same harness scores it. Ask Claude to review it for leakage (e.g. normalisation fitted on test data) and other bugs, not to write it.
  *Done when:* it is scored in the RP-23 table, and the review has found no leakage.

- [ ] **RP-26 · ADR: ML detection decision**
  **Both** · Claude draft; You decide · Depends: RP-25 · Closes: ROADMAP 2.1 "ML detection"
  *Steps:* does any ML detector beat `SeasonalRobustZ` on false alarms and lead time, and not just F1? And can its findings still be cited? Record the answer in `docs/adr/MLDetection.md`. "No" is a result and closes the item.
  *Done when:* the ADR is committed and the roadmap ticked.

- [ ] **RP-27 · Embeddings for Smriti**
  **Both** · You 3 h reading; Claude 1 session; You decide · Depends: RP-12 · Closes: ROADMAP 2.5 recall item
  *Steps:*
  1. **You** read about sentence embeddings, the MTEB leaderboard, BM25, recall@k and MRR.
  2. **Claude** builds the incident pairs (same cause with different wording; different cause with the same wording), then compares `HashingEmbedder`, BM25 and a small local sentence-embedding model behind the `Embedder` protocol, reporting recall@k **and** false precedents.
  3. **You** adopt or reject the new embedder.
  *Done when:* the table exists and the decision is recorded.

### Block E — Paper completion

- [ ] **RP-28 · §2 Related work, final**
  **Both** · Claude 1 session; You 4 h · Depends: RP-03, RP-11, RP-19 entries (20+)
  *Steps:* Claude organises the log into themes (AIOps/RCA, LLM agents, agent security, runbook automation, safe constrained agency) and drafts the connecting prose. You rewrite it, and check every claim against the paper it cites.
  *Done when:* §2 is written, and every citation is in the log.

- [ ] **RP-29 · §10, abstract, contributions**
  **Both** · You 4 h · Depends: RP-18, RP-21
  *Steps:* derive the conclusion from §8, not from the hopes in §1. Rewrite the abstract and the contribution list to claim exactly what was measured.
  *Done when:* no claim in the abstract lacks a table behind it.

- [ ] **RP-30 · Reproducibility**
  **Claude** · 1 session · Depends: all result tasks
  *Steps:* one command regenerates every table and figure from the records. Fill the NeurIPS / AAAI reproducibility checklist into `docs/research/REPRODUCIBILITY.md` with model versions, Ollama version, GPU, temperatures, seeds, dataset versions and licences. Do a clean-checkout rerun of the table generation.
  *Done when:* the clean rerun matches the committed tables exactly.

- [ ] **RP-31 · External review and venue decision**
  **You** · 4 h + waiting · Depends: RP-29
  *Steps:* send the draft to one person outside the project and ask them to break the claims. Fix what they find, or state it as a limitation. Then decide between an arXiv preprint, an AIOps / ML-systems workshop, or a software-engineering venue.
  *Done when:* the review has been answered and the venue chosen. This is your call; the roadmap deliberately does not make it for you.

---

## Calendar

Your hours only. Claude tasks show as **[ask: RP-xx]**, which is the moment
to start that session; the hours beside it are your review time.
🌙 = leave the machine on overnight.

### Week 1 · Oct 12–18 — foundations, free results
| Day | Task | h |
|---|---|---|
| Mon 12 | Bring the kind cluster up; **[ask: RP-01]** 🌙 | 1.5 |
| Tue 13 | RP-02 Karpathy GPT video, part 1, coding along | 1.5 |
| Wed 14 | RP-02 Karpathy, part 2 | 1.5 |
| Thu 15 | RP-02 Karpathy, finish; review RP-01 results | 1.5 |
| Fri 16 | RP-02 Illustrated Transformer + *Attention* §3 | 1.5 |
| Sat 17 | RP-02 one-page note; **[ask: RP-03]** scaffold; read Ahmed et al. | 3 |
| Sun 18 | RP-03 read RCACopilot; fill 2 entries | 2 |

### Week 2 · Oct 19–25 — sampling and the arm design
| Day | Task | h |
|---|---|---|
| Mon 19 | RP-03 ReAct | 1.5 |
| Tue 20 | RP-03 Greshake et al.; RP-03 done | 1.5 |
| Wed 21 | RP-04 HF course: generation and sampling | 1.5 |
| Thu 22 | RP-04 structured output; read `gateway.py` | 1.5 |
| Fri 23 | RP-04 `openaicompat.py` + Ollama API; done | 1.5 |
| Sat 24 | **[ask: RP-05]**; review the ADR draft; make your decisions | 3 |
| Sun 25 | RP-05 finalise and commit; slack | 2 |

### Week 3 · Oct 26 – Nov 1 — build the LLM arms
| Day | Task | h |
|---|---|---|
| Mon 26 | **[ask: RP-06]** | 0.5 |
| Tue 27 | RP-11 start: HELM framing | 1.5 |
| Wed 28 | Review the RP-06 diff, part 1 | 1.5 |
| Thu 29 | Review the RP-06 diff, part 2; request fixes | 1.5 |
| Fri 30 | RP-07 pull the models | 0.5 |
| Sat 31 | **[ask: RP-07]**; inspect the 6 records by hand with Claude | 3 |
| Sun 1 | RP-11 Husain on evals | 2 |

### Week 4 · Nov 2–8 — run the arms *(checkpoint Sun 8)*
| Day | Task | h |
|---|---|---|
| Mon 2 | **[ask: RP-08]** — commit the matrix, start the batch 🌙 | 1 |
| Tue 3 | RP-09 Dror et al. 🌙 | 1.5 |
| Wed 4 | RP-09 Dror et al., finish; check batch progress 🌙 | 1.5 |
| Thu 5 | RP-11 contamination reading; log 3 entries | 1.5 |
| Fri 6 | Review the RP-08 tables | 1.5 |
| Sat 7 | **[ask: RP-09]**; read the significance results | 3 |
| Sun 8 | **Checkpoint.** RP-11 done | 2 |

### Week 5 · Nov 9–15 — §7 arms; start the corpus
| Day | Task | h |
|---|---|---|
| Mon 9 | **[ask: RP-10]** draft | 0.5 |
| Tue 10 | RP-10 rewrite, part 1 | 1.5 |
| Wed 11 | RP-10 rewrite, part 2; check against the tables | 1.5 |
| Thu 12 | RP-12 incident specs 1–3 | 1.5 |
| Fri 13 | RP-12 specs 4–6 | 1.5 |
| Sat 14 | RP-12 specs 7–12 | 3 |
| Sun 15 | RP-12 review all 12; **commit the answer keys alone** | 2 |

### Week 6 · Nov 16–22 — diagnosis tooling
| Day | Task | h |
|---|---|---|
| Mon 16 | **[ask: RP-12 fixtures]** | 0.5 |
| Tue 17 | Review the fixtures against your specs | 1.5 |
| Wed 18 | **[ask: RP-13]** | 0.5 |
| Thu 19 | Review RP-13 | 1.5 |
| Fri 20 | RP-15 reading: calibration | 1.5 |
| Sat 21 | **[ask: RP-14]** 🌙; read the first results | 3 |
| Sun 22 | RP-14 table review | 2 |

### Week 7 · Nov 23–29 — *light: Thanksgiving*
| Day | Task | h |
|---|---|---|
| Mon 23 | RP-14 write the Phase 2 verdict | 1.5 |
| Tue 24 | **[ask: RP-15]** 🌙 | 0.5 |
| Wed 25 | Review RP-15 | 1 |
| Thu 26 | — | 0 |
| Fri 27 | — | 0 |
| Sat 28 | RP-15 paragraph on whether confidence is a safe risk input | 2 |
| Sun 29 | slack | 0 |

### Week 8 · Nov 30 – Dec 6 — §7 diagnosis
| Day | Task | h |
|---|---|---|
| Mon 30 | **[ask: RP-16]** draft | 0.5 |
| Tue 1 | RP-16 rewrite | 1.5 |
| Wed 2 | RP-16 rewrite; check against the tables | 1.5 |
| Thu 3 | **[ask: RP-17 extract]** | 0.5 |
| Fri 4 | RP-17 categorise the failures | 1.5 |
| Sat 5 | RP-17 categorise the failures | 3 |
| Sun 6 | RP-17 finish; Claude tabulates | 2 |

### Week 9 · Dec 7–13 — §8
| Day | Task | h |
|---|---|---|
| Mon 7 | RP-18 OpenRCA failure section | 1.5 |
| Tue 8 | RP-18 AIOpsLab failure section | 1.5 |
| Wed 9 | RP-18 outline | 1.5 |
| Thu 10 | RP-18 draft | 1.5 |
| Fri 11 | RP-18 draft | 1.5 |
| Sat 12 | RP-18 finish; tick the roadmap | 3 |
| Sun 13 | RP-19 read OpenRCA | 2 |

### Week 10 · Dec 14–20 — benchmark choice *(checkpoint Sun 20)*
| Day | Task | h |
|---|---|---|
| Mon 14 | RP-19 read RCAEval | 1.5 |
| Tue 15 | RP-19 read AIOpsLab | 1.5 |
| Wed 16 | RP-19 read ITBench; **[ask: RP-19 feasibility]** | 1.5 |
| Thu 17 | RP-19 decide; commit the ADR | 1.5 |
| Fri 18 | Log entries for all four | 1.5 |
| Sat 19 | **[ask: RP-20]**; review | 3 |
| Sun 20 | **Checkpoint.** Re-read §7 and §8 together | 2 |

### Week 11 · Dec 21–27 — buffer
Catch-up only. If nothing slipped: RP-22 reading starts early.

### Week 12 · Dec 28 – Jan 3 — external run; ML reading *(light: New Year)*
| Day | Task | h |
|---|---|---|
| Mon 28 | **[ask: RP-21 run]** 🌙 | 0.5 |
| Tue 29 | RP-22 scikit-learn MOOC: pipelines | 1.5 |
| Wed 30 | RP-22 MOOC: evaluation | 1.5 |
| Thu 31 | — | 0 |
| Fri 1 | — | 0 |
| Sat 2 | RP-21 write the §7 subsection and the §9 update | 3 |
| Sun 3 | RP-22 Isolation Forest paper | 2 |

### Week 13 · Jan 4–10 — classical ML
| Day | Task | h |
|---|---|---|
| Mon 4 | RP-22 Wu & Keogh; done | 1.5 |
| Tue 5 | **[ask: RP-23]** | 0.5 |
| Wed 6 | RP-24 PyTorch basics, part 1 | 1.5 |
| Thu 7 | RP-24 PyTorch basics, part 2 | 1.5 |
| Fri 8 | Review the RP-23 table | 1.5 |
| Sat 9 | RP-24 3Blue1Brown; write a training loop from memory | 3 |
| Sun 10 | RP-25 design your autoencoder | 2 |

### Week 14 · Jan 11–17 — deep learning; decisions *(checkpoint Sun 17)*
| Day | Task | h |
|---|---|---|
| Mon 11 | RP-25 code | 1.5 |
| Tue 12 | RP-25 code and train | 1.5 |
| Wed 13 | RP-25 wrap as a strategy; ask Claude for a leakage review | 1.5 |
| Thu 14 | RP-25 fixes; score it | 1.5 |
| Fri 15 | RP-27 embeddings reading; **[ask: RP-27]** | 1.5 |
| Sat 16 | **[ask: RP-26 draft]**; decide; commit the ADR | 3 |
| Sun 17 | **Checkpoint.** RP-27 decide | 2 |

### Week 15 · Jan 18–24 — writing
| Day | Task | h |
|---|---|---|
| Mon 18 | **[ask: RP-28 draft]** | 0.5 |
| Tue 19 | RP-28 rewrite §2 | 1.5 |
| Wed 20 | RP-28 rewrite §2; check citations | 1.5 |
| Thu 21 | RP-29 §10 | 1.5 |
| Fri 22 | RP-29 abstract and contributions | 1.5 |
| Sat 23 | **[ask: RP-30]**; full read-through of the paper | 3 |
| Sun 24 | Fixes from the read-through | 2 |

### Week 16 · Jan 25–31 — review and decide
| Day | Task | h |
|---|---|---|
| Mon 25 | RP-31 send to the reviewer | 0.5 |
| Tue 26 – Fri 29 | Slack for anything late; respond as feedback arrives | 1.5/day |
| Sat 30 | RP-31 address the review | 3 |
| Sun 31 | RP-31 decide the venue | 2 |

---

## What you will be able to say at the end

- How a transformer turns tokens into a next-token distribution, and why that
  makes runs non-deterministic — with a GPT you coded yourself.
- How to evaluate an LLM system without fooling yourself — done on your own
  system, with significance tests and calibration.
- Classical ML and deep-learning detectors built and fairly compared against
  strong statistical baselines, with the decision recorded, and a deep model you
  wrote yourself.
- Embeddings and retrieval measured, not assumed.
- A paper whose central comparison has an LLM in it, whose diagnosis claim has a
  number, and whose self-authored benchmark is backed by one that is not.

**Deferred deliberately:** LoRA fine-tuning of a 7B model. It becomes worth doing
only after RP-14 gives a diagnosis number it could improve.
