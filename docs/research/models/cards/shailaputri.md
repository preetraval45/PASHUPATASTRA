# Model card — Shailaputri v0 (`sati-shailaputri-v0`)

Format follows Mitchell et al. (2019). The numbers below are a snapshot. The
generated table [shailaputri.md](../shailaputri.md) is the source of truth.

## Model details

- **What it does:** scores each new point of a metric series for how
  anomalous it is relative to that series' own past. Model 1 of the nine Sati
  models ([adr/Navadurga](../../../adr/Navadurga.md)).
- **Type:** a LightGBM binary classifier over **strictly causal** features:
  - robust z-scores against rolling baselines over the previous 12, 72 and
    288 points;
  - the change from the previous point, the short-to-long volatility ratio,
    and the same time one day earlier.

  Every rolling statistic is shifted by one point, so a value is never part
  of its own baseline. A test proves that changing future values never
  changes a past feature.
- **Threshold:** chosen on training families only, over 0.30 to 0.95.
- **Built by:** an AI assistant (Claude), under the owner's direction.
- **Licence:** Apache-2.0. NAB is MIT.

## Intended use

- **A second opinion beside the statistical detector.** Agreement between the
  two raises confidence ([adr/SatiDetect](../../../adr/SatiDetect.md)).
- **Out of scope:** paging a person on its own. At more than 200 false alarms
  per 1000 points under NAB's labelling, it is not quiet enough. The same
  holds for every detector measured.

## Data and splits

NAB, real series only: 47 series in five families (AWS CloudWatch, ad
exchange, known-cause failures, traffic, tweets). It is evaluated **leave one
family out**: trained on four families and tested on the fifth. It is scored
online by the same harness as the four statistical strategies, on the same
series.

## Metrics (snapshot, run 39169841856; mean across held-out families)

| Detector | F1 | Recall | False alarms / 1000 | Lead |
|---|---:|---:|---:|---:|
| Shailaputri v0 | 0.457 | 0.824 | 226.5 | 195 |
| seasonal-robust-z | 0.312 | 0.761 | 228.7 | 241 |
| seasonal-naive | 0.346 | 0.930 | 372.2 | 240 |

## Known limitations

- **It flags later** than the statistical detectors (lead 195 vs about 240).
  It was trained to recognise points inside the window, not the window's
  onset.
- **NAB's labelling:** labels are windows, and Wu & Keogh (2021) document
  trivial and questionable series. The numbers inherit both.
- **Univariate only.** Multivariate data (SMD) is v1.

## Ethical considerations

A detector that cries wolf trains people to ignore it. Its false-alarm rate is
reported next to its F1 everywhere it appears.
