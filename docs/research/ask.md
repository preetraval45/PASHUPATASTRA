# Sati AI answers: accuracy

How often Sati AI's general answers are right, measured on question sets written before the results
(`benchmark/ask/`), with `scripts/askeval.py`. An answer is correct when it contains an accepted string
at a word start; a decline is correct only where a decline is the right answer. Abstentions count as
misses.

## 22 Nov 2026 — answers read from the open web (RP-109)

Until now Sati AI answered from its security knowledge base only, and that base answered anything
that shared a word with it: "Who discovered penicillin?" returned an ATT&CK technique, "How does a
rainbow form?" returned *Rainbow Table Password Cracking*. Its score was normalised against its own
best hit, so the top hit always looked answerable.

Now Wikipedia is read for every general question (the top six articles, the first two in full), and
the knowledge base answers only when one of its entries covers the question at least as well as the
best web passage does, measured the same way on both sides. Every web answer quotes its passage and
links its page.

**test2** (44 questions, written after `test` had been read while fixing bugs; measured once per
version, never tuned on):

| Version | General (n = 35) | Security (n = 9) | All (n = 44) |
|---|---|---|---|
| Live API before this change | 0.057 (0.016–0.186) | 0.889 (0.565–0.980) | 0.227 (0.128–0.370) |
| Web reading, hand-set ranking | **0.857** (0.706–0.937) | 0.889 (0.565–0.980) | **0.864** (0.733–0.936) |

**test** (46 questions): the live API scored 0.033 general, 0.875 security, 0.326 overall. The first
web version, reading introductions only, scored 0.800, 0.875 and 0.826. That set was then read while
fixing two general bugs ("blockchain" routed as a defence question; a film outranking the article it
was named after), so its later numbers are not clean and it is not used again.

Known scorer strictness: on test2, "What is a computer worm?" was answered with NIST's definition
("can propagate itself"), which none of its accepted strings match. It counts as wrong.

## What limits it

- **Reading, not finding.** The passage is chosen by keyword coverage, title fit and phrase overlap.
  "What is the capital of France?" still picks *Capital punishment in France*. The next step is
  Brahmacharini's passage ranker, trained on Natural Questions (`sati.webqa`), which is served only
  if it beats the hand-set score on held-out questions.
- **Only Wikipedia by default.** A self-hosted SearXNG instance (`PASHU_WEB_SEARCH_URL`) adds the
  general web; it needs a host.
