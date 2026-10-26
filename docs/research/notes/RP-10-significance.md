# RP-10 — Testing whether a difference is real

Study notes and a code map prepared for the owner's RP-10 learning task: read
Dror, Baumer, Shlomov and Reichart, *The Hitchhiker's Guide to Testing
Statistical Significance in Natural Language Processing* (ACL 2018). The
task is done when **you** can answer the last section in your own words. This
file is something to read beside the paper and argue with, not a
replacement for it.

Where this note summarises the paper, check it against the paper itself.
Disagreeing with a summary is part of the exercise.

## 1. What the paper argues

- **The problem.** Comparisons are usually reported as "A scored higher than
  B" with no test of whether the gap could be chance. When a test is reported,
  its assumptions often do not hold for the metric.
- **What to do.** Choose the test from what the metric is and how the data is
  paired. The paper sorts tests into families:
  - **Parametric**, such as the paired t-test. These need distributional
    assumptions, typically approximate normality, that many NLP metrics do
    not meet.
  - **Non-parametric, sampling-free**, such as the sign test, McNemar's test
    and Wilcoxon's signed-rank test. These suit paired, per-item outcomes.
  - **Non-parametric, sampling-based**, such as permutation tests and the
    bootstrap. These suit metrics with no simple closed form.
- **Report the test, not only the score.**

## 2. Where each idea is in this repository

| Idea | Where it lives | In Table 5 |
|---|---|---|
| Paired data: the same scenarios and run index faced by both arms | `scripts/papertables.py`, `compare()` pairs on `(scenario_id, run_index)` | Every row |
| McNemar's exact test for paired right/wrong outcomes | `pashupatastra/significance.py`, `mcnemar()` | "A right only / B right only", "McNemar p" |
| Bootstrap for a metric with no closed form (FRR) | `significance.py`, `bootstrap_difference()`, resampling **scenarios**, not runs | "FRR(A) − FRR(B), 95% CI" |
| Many comparisons at once | `significance.py`, `holm()` (added 26 October) | "Holm-adjusted p", and the verdict |

Two choices here go slightly beyond the basic recipe:

- **Resampling scenarios, not runs.** The three runs of one scenario are
  correlated. Resampling runs as if they were independent makes every
  interval too narrow.
- **The Holm correction.** Table 5 runs about ten tests. At 0.05, roughly one
  in twenty would "survive" by chance alone. The paper's authors treat
  multiple comparisons across datasets separately, in *replicability
  analysis*; Holm is the simplest control for a single table.

## 3. Reading our Table 5 with this in mind

- **"Within chance" does not mean "equal".** pashupatastra-llm against
  naive-llm with llama3 shows 0 / 0 discordant runs: no evidence either way,
  because the arms never disagreed.
- **Discordant pairs carry all the information.** With qwen2.5:7b the arms
  disagreed on only 6 runs (1 / 5). No test can find a difference in 6 runs
  unless it is overwhelming.
- **"Undefined (no actions)" is honest.** FRR has no value when nothing was
  executed, so neither does a bootstrap interval on it.

## Check yourself (the done-when)

Answer each in your own words. A sentence or two is enough.

1. Why is McNemar's test, and not a two-sample proportion test, the right
   test for "pashupatastra vs runbook: 18 / 0"? What would ignoring the
   pairing throw away?
2. Our bootstrap resamples **scenarios** and keeps all three runs of each.
   What goes wrong if it resampled the 93 runs independently instead?
3. A row passes at raw p = 0.03 but fails after Holm. Explain to a reviewer
   why the second verdict is the one to report.
4. Which of the paper's test families would you use for a new metric, such
   as Mahagauri's premature all-clear rate compared across two verifiers on
   the same incidents? Why?

Log the paper in [related-work.md](../related-work.md) with your answers.
