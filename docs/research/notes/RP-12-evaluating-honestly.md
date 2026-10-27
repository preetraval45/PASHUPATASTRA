# RP-12 — Evaluating ML systems honestly

Study notes for the owner's RP-12 learning task. It is done when **you** can
list the leakage types Kapoor & Narayanan describe and say which ones this
project is exposed to. So read the three sources first. Then use the map in
§4 to check your answer against this repository, and correct the map where
you disagree.

## 1. Kapoor & Narayanan 2023 — the one to read closely

*Leakage and the Reproducibility Crisis in Machine-Learning-based Science*,
Patterns 4(9). They surveyed published work across many fields that use ML
and found leakage in hundreds of papers. Their taxonomy has three families
and eight types:

| Type | What goes wrong |
|---|---|
| **L1.1** No test set | Performance is reported on the data the model was fit or tuned on. |
| **L1.2** Pre-processing on train and test together | Normalisation, imputation or resampling fitted on all the data, so test statistics leak into training. |
| **L1.3** Feature selection on train and test together | Features are chosen by looking at how they relate to the outcome on the test data. |
| **L1.4** Duplicates | The same (or a near-identical) sample sits on both sides of the split. |
| **L2** Illegitimate features | A feature is a proxy for the outcome and would not be available, or would not mean the same, at prediction time. |
| **L3.1** Temporal leakage | The test set holds data from before some training data, so the model "sees the future". |
| **L3.2** Non-independence between train and test | Samples from the same patient, machine, source or system on both sides, so the test measures recognition, not generalisation. |
| **L3.3** Sampling bias in the test set | The test distribution is not the one the claim is about. |

Their remedy is a **model info sheet**: for each claim, state how each type is
ruled out. §4 below is a first draft of one for this project.

## 2. Hamel Husain on evals — error analysis first

His posts (*Your AI Product Needs Evals*, and the field guide) make one
argument. Look at real outputs before choosing any metric. Write down the
failures you see, group them into categories, and count them. Only then
automate checks for the categories that matter. A metric chosen first measures
what was easy to measure. RP-34's review sheet ([review/rp34-failures.md](../review/rp34-failures.md))
is this step done for RCAEval: 200 wrong answers, each with a category for you to assign.

## 3. Liang et al. 2022 (HELM) — the framing

*Holistic Evaluation of Language Models*. One accuracy number hides what
matters, so evaluate many scenarios against many metrics: accuracy,
calibration, robustness, fairness, bias, toxicity and efficiency. Use
standardised prompts, and publish every raw output. Its lesson here is
**report the whole table, including the rows that look bad**. The paper's §7
tables and the /findings page follow that: the negative results get the same
space as the positive ones.

## 4. Draft model info sheet for this project — check it

✓ means ruled out by a mechanism you can point at. ⚠ means exposed or only
partly guarded. **The ⚠ rows are your answer to the done-when question.**
Confirm or correct each one.

| Type | Where it could bite here | Status |
|---|---|---|
| L1.1 | Thresholds and epochs are chosen on validation groups, never on test (Shailaputri `choose_threshold`, Brahmacharini epochs, Mahagauri `choose`). | ✓ |
| L1.2 | RCA features compare each series to its *own* pre-fault window (`sati/rca/features.py`), so nothing is fitted across cases. Check the detectors yourself: is any scaler fitted on test series? | ✓ for RCA; **check** detectors |
| L1.3 | The feature lists are fixed in code before runs (`kaal.FEATURES`, `feature_columns`); none is chosen by test performance. | ✓ |
| L1.4 | Kaal's guard drops test incidents whose signature appears in training (RP-18), and Kushmanda's corpus is MinHash-deduplicated. RCAEval has repeated runs of the same fault on the same service. | ✓ Kaal / LM; ⚠ RCAEval repetitions |
| L2 | The RCAEval adapter's output is test-checked to carry no label. The live set's `deploy_before` is observable, but the release fault is the only one that deploys, so it partly encodes the fault type. | ✓ adapter; ⚠ `deploy_before` |
| L3.1 | NAB and SMD are split in time order, and Kalaratri by time. | ✓ |
| L3.2 | Splits are leave-one-system-out (RCAEval), by machine group (SMD), by source (Brahmacharini, Skandamata) and by entity (Kushmanda). The CIC-IDS2017 random split shows this leakage live: F1 0.997 at random, against 0.453 on unseen attack days. | ✓ (a measured example) |
| L3.3 | The RCAEval subset is Online Boutique and Sock Shop only (Train Ticket has no authored graph). PIB scenarios were written by this project. | ⚠ both |

## 5. Questions to answer in your own words

1. Which ⚠ row would most change a headline number if it were fixed, and why?
2. Katyayani's 0.930 on RCAEval is leave-one-system-out. Which leakage type does that split guard against, and which does it not?
3. Why does a random split on CIC-IDS2017 inflate F1? Name the type.
4. What would you put in a model info sheet for Kushmanda's 0.528 exact match?
