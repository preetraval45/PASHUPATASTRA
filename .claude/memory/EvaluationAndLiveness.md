# Evaluation published, and a counter that had been double-counting

- **Date:** 2026-10-07
- **Phase:** Phase 5G — Reachable, then convincing
- **Commit(s):** `5bdb010` (R124), `3ff3187` (R125)

## What changed

`/evaluation` exists and publishes the venue review of the paper in full, each
finding beside what has closed it. `pashupatastra/diagnosis.py` is the grader
the benchmark never had. `components/live.tsx` — written at R61 and mounted
nowhere since — is now on `/overview` and `/observatory`, and the page-view
counter underneath it was found to be wrong in two independent ways and fixed
at the rule rather than the symptom.

## Why

The owner forwarded a venue review (IEEE S&P / USENIX / CCS / ICSE class). Its
verdict: the writing is publishable, the evaluation is not. Five findings, the
largest being that **the language model is never tested** — the benchmark
substitutes a deterministic stand-in, so nothing measures whether the diagnoses
are correct.

The tempting response is to improve the page that describes the evaluation. The
page is therefore built so that is impossible: every figure is recounted by
`scripts/buildevaluation.py` from the corpus, the harness's declarations and
`benchmark/results/`, and `verifyevaluation.py` recounts them again from source
without reading the manifest.

## Decisions made

- **The review is published as given, not summarised.** Three of five findings
  are open and render as open. A reviewer who finds a gap themselves concludes
  the project did not know; one who finds it stated concludes it measured. This
  rules out the usual "roadmap written in the direction of the criticism".
- **Diagnosis is graded by string identity over a closed label set** — never by
  a model judging a model, which rule 1 forbids, and never fuzzily, which would
  have the grader take the decision the model was asked to take. The corpus
  turned out to make this clean: 60 scoreable scenarios with 60 *distinct* root
  causes, so it is a one-in-sixty choice with a 1.7% baseline.
- **The 44 do-nothing/escalate scenarios are excluded, not scored as misses.**
  Counting them would punish an arm for being right and drag any accuracy toward
  a third of its true value. Held by a named negative-control test.
- **Chain credit is never folded into top-1**, and `above_chance` is false
  unless the Wilson floor clears the baseline. An accuracy at n=60 without an
  interval is not a result.
- **`<Live />` is not on `/impact`.** Its data is daily-grain project history
  and does not move while you read it. The inflation reason that first ruled it
  out was fixed in the counter, but the "motion for its own sake" reason stands.
- **The view counter counts arrivals, and paths without a dot.** Measured with
  a header probe and a real browser, not reasoned about.

## What the measurement actually found

Two faults, one of them shipped months ago:

1. **`.webp` was missing from the middleware matcher's exclusion list**, and the
   logo is a `.webp` on every page. **Every visit since R107 was counted twice**,
   and `by_route` carried `/logo.webp` as somewhere a reader could go. The
   headline figure on `/impact` has been roughly double the truth. Fixed by
   excluding any path containing a dot, so the next asset format cannot
   reintroduce it — an allow-list of extensions is what went stale.
2. **`router.refresh()` was counted as a render**, so mounting a live panel
   would have driven `/impact`'s own headline up four times a minute for as long
   as a tab stayed open.

Also found: **all six declared arms have no recorded runs**, and
`benchmark/results/` is gitignored — so the run records behind any table in the
paper live only on the machine that produced them. The review said two of four
arms lacked data; on this checkout it is six of six.

## Open questions

- **Is `/impact`'s historical view count worth correcting or annotating?** It
  has been roughly 2× since R107. The store holds the per-route breakdown, so
  `/logo.webp` could be subtracted — but a retrospective edit to a published
  figure needs saying out loud rather than doing quietly.
- **Should `benchmark/results/` be committed?** A reviewer cannot recompute a
  published number without it. It is a decision about size, and about whether a
  run on one person's cluster is worth citing at all.
- **No cluster and no model run yet.** The grader exists and has never graded
  anything. The run needs the five-service injection stack; `kubectl` is present
  via Docker Desktop but Kubernetes is not enabled.

## Next session should

- **Run the model arm.** `qwen2.5:7b`, `mistral` and `llama3` are on local
  Ollama with a 16 GB RTX 5070 Ti. The diagnosis task needs no cluster at all —
  it is a closed-set choice over scenario briefs — so top-1 accuracy with its
  Wilson interval can be produced *without* standing up Kubernetes. That is the
  cheapest path to closing the review's biggest finding, and the grader is
  already written and tested.
- Coordinate first: session `pashupatastra-9a` held the GPU on 7 Oct for a live
  indirect-injection experiment (8 payloads × 3 incidents × 3 runs × 3 models)
  and asked that no other Ollama models be loaded until it finished. Its results
  belong beside this work — it also ran a worst-case attacker-controls-output
  test through `/agent/chat`: 147 turns, **0 execution records, 0 approvals**.
- Then wire the injection numbers into `/evaluation`'s review section, which
  currently reads "measured at the chat route" for that finding.
