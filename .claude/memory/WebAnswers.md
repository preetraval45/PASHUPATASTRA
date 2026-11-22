# Sati AI answers from the open web (RP-109)

- **Date:** 2026-11-22
- **Phase:** Product — Sati AI general answers
- **Commit(s):** this push

## What changed

General questions are answered from Wikipedia (and SearXNG when `PASHU_WEB_SEARCH_URL` is set), ranked by the project's own scoring, quoted with links. `pashupatastra.webread` (core, stdlib only) holds fetch, passages and FEATURES so training and serving share them; `providers/web.py` adds SearXNG, page fetching and the served ranker (`sati_models/brahmacharini_ranker.json`, exported by the `brahmacharini-ranker` CI job only if it beats `webread.heuristic` on NQ-open validation). Production sets `PASHU_WEB_SOURCES=wikipedia` in deploylambda.

## Why

Owner wants Sati to answer anything, accurately, with the Navadurga models staying the owner's own (no outside LLM) and reaching the whole web, not only Wikipedia.

## Decisions made

- **Measure before tuning:** `benchmark/ask/dev.yaml` is for tuning; `test.yaml` was read while fixing bugs, so it's retired; `test2.yaml` is the clean held-out set. Never change accept strings after a result.
- **KB vs web is compared on the same measure** (`webread.quality`: coverage + title fit); curated paths (HARMFUL, tactic, glossary, concept, mitigation) stay KB-first.
- **Hand-tuning stopped at dev ~0.83–0.87:** weight changes traded questions; the trained ranker replaces it.
- **MediaWiki booleans:** any value (even 0) turns `exintro` on — omit the key for full text.
- Heredocs with `\b` inside non-raw Python strings wrote backspace characters into web.py once; write regex edits with the Edit tool or a script file.

## Open questions

- SearXNG host (Oracle box?) — owner's decision.
- Locally, core tests testsmriti/testdiagnosis/testpib/testlearning fail (39) and api testexcessiveagency route test fails, with or without this change; CI is the judge.

## Next session should

- Read the brahmacharini-ranker CI results; if served, rerun `python scripts/askeval.py --set test2` against the deployed API and add the row to docs/research/ask.md.
- Train a reader (span extraction, SQuAD 2.0 CC BY-SA 4.0) on Kaggle so answers lead with the short answer.
