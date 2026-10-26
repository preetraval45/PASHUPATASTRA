# Results round, 26 Oct evening

- **Date:** 2026-10-26
- **Phase:** Blocks B, E, H
- **Commit(s):** pending

## What landed

- **Sim-to-real fails.** The Kaal-trained ranker scores 0.490 (OB) and
  0.265 (SS) zero-shot, below loudest-service (0.608 / 0.747). Katyayani
  trained on real RCAEval scores 87.9%. Conclusion: train Sati-RCA on real
  data; Kaal is augmentation at most.
- **SatiDetect re-decided.** It wins false alarms (26.6 against 74.7) and
  loses lead time (180 against 241), so the decision is unchanged with new
  reasons.
- **Siddhidatri.** Fusion F1 equals Shailaputri alone. It buys recall with
  twelve times the false alarms and is worse calibrated. RP-73 is done, as a
  negative result.
- **Kushmanda v2.** It answers from passages well (ROUGE-L 0.79–1.00),
  declines on 54% of unanswerable questions, and copies IDs badly (0.53
  against lexical 0.96). It has a card. Serving must verify IDs against the
  cited passage.
- **The benchmark bot overwrote tables.md** with a pre-Holm format and new
  qwen/mistral counts. I regenerated it with Holm, and the §7.1 guard test
  caught four stale numbers, now fixed.
- **RP-39, 60, 73 and 74 are ticked.** All 14 tables reproduce.

## Next session should

- On the next train-sati run, confirm Shailaputri's model hash equals
  `062909b7`, proving the thread pin works.
- RP-44: serve Kushmanda behind the sati provider with ID verification.
