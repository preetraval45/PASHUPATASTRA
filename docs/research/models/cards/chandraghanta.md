# Model card — Chandraghanta v0 (`sati-chandraghanta-v0`)

Format follows Mitchell et al. (2019). The generated table
[chandraghanta.md](../chandraghanta.md) is the source of truth; the numbers
below are a snapshot of the 26 Oct Kaggle run.

## Model details

- **What it does:** flags network flows that look like attack traffic. Model 3
  of the nine Sati models ([adr/Navadurga](../../../adr/Navadurga.md)).
- **Type:** a LightGBM binary classifier over each flow's own features (bytes,
  packets, durations, flags, rates). Its threshold is chosen on a validation
  slice of the training data, never the test.
- **Baseline:** PCA reconstruction error fitted on benign training flows only
  (Lakhina et al., SIGCOMM 2004). It needs no attack labels.
- **Built by:** an AI assistant (Claude), under the owner's direction.
- **Weights: not published.** Both datasets are licensed for research use
  ([datasheets.md](../../datasheets.md)), and releasing weights is the
  owner's decision.

## Intended use

- **For:** research and evaluation. In particular, it measures how much
  published intrusion-detection results depend on the evaluation split.
- **Out of scope:** production alerting. Both datasets come from lab
  testbeds; a model trained here has learned those testbeds' traffic.

## Data and splits

| Dataset | Split | Train flows | Test flows | Attacks in test |
|---|---|---:|---:|---:|
| UNSW-NB15 | the official training and testing files | 175,341 | 82,332 | 55.1% |
| CIC-IDS2017 | by day: Monday to Wednesday train, Thursday and Friday test | 1,668,530 | 1,162,213 | 25.1% |

UNSW-NB15's released file names are swapped relative to the paper, so the
training file is chosen by size and recorded in the results. On CIC-IDS2017,
every test attack family (bot, DDoS, infiltration, port scan, web attacks)
appears only on the test days.

## Metrics

| Dataset | Detector | Precision | Recall | F1 | False-positive rate |
|---|---|---:|---:|---:|---:|
| UNSW-NB15 | Chandraghanta v0 | 0.821 | 0.988 | 0.897 | 0.263 |
| UNSW-NB15 | without TTL fields | 0.827 | 0.981 | 0.897 | 0.252 |
| UNSW-NB15 | PCA, benign-only | 0.581 | 0.993 | 0.733 | 0.878 |
| CIC-IDS2017 | Chandraghanta v0, unseen days | 0.989 | 0.294 | 0.453 | 0.001 |
| CIC-IDS2017 | PCA, benign-only | 0.440 | 0.135 | 0.207 | 0.058 |
| CIC-IDS2017 | Chandraghanta v0, random split *(reference only)* | 0.998 | 0.996 | 0.997 | 0.0005 |

## What the numbers say

- **The split decides the headline.** On CIC-IDS2017, the same model scores
  F1 0.997 on a random split and 0.453 when the test attacks are families it
  has never seen. A random split can put flows from the same attack sessions
  in both training and test. Results reported that way measure recognition of
  known traffic, not detection of new attacks.
- **It generalises to some families, not others.**
  - Generalises: web attacks (brute force 0.91, XSS 0.97, SQL injection 1.00
    of 21 flows) and DDoS (0.64), which resemble the brute-force and DoS
    traffic seen on the training days.
  - Misses almost entirely: port scans (0.01), bots (0.00) and infiltration
    (0 of 36). These look like nothing it trained on.
  - The benign-only PCA baseline catches more of the infiltration flows
    (0.72) and nothing of the web attacks.

  The two detectors fail differently, which seemed to argue for running both.
- **Running both did not pay (v1, Kaggle run of 27 Oct).** Flagging a flow
  when *either* detector does catches the infiltration flows (0.722) and
  keeps the web attacks. It also flags 0.058 of the 871,074 benign flows
  instead of 0.001, so F1 on unseen days falls slightly (0.449 against 0.453)
  and precision drops from 0.989 to 0.660. On UNSW-NB15, F1 falls from 0.897
  to 0.733. The PCA detector's false alarms cost more than the attacks it adds.
  v0 stays the model to serve; v1 is kept as a recorded negative result.
- **TTL is not doing the work here.** The literature flags UNSW-NB15's TTL
  fields as near-labels. Removing them leaves F1 unchanged (0.897 both ways).
- **UNSW-NB15's official test set is hard on false alarms.** One normal flow
  in four is flagged. The official files differ in distribution, and a
  threshold chosen on training data does not carry over. As an alerting
  system, it would be unusable at this rate.

## Known limitations

- Lab traffic only: IXIA-generated attacks (UNSW-NB15) and a scripted
  testbed (CIC-IDS2017).
- CIC-IDS2017 has documented labelling and flow-construction errors
  (Engelen et al., 2021). The run uses the original CSVs and inherits them.
- Recall for small families rests on few flows: SQL injection (21) and
  infiltration (36).

## Ethical considerations

Only aggregate flow statistics are used. There are no payloads and no
addresses: the mirror's MachineLearningCVE files carry no IPs.
