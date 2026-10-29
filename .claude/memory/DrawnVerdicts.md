# Specialist verdicts drawn; 0.2.0 retrain numbers

- **Date:** 2026-10-29
- **Phase:** Phase 0 — Foundation (Sati AI)
- **Commit(s):** pending

## What changed

`runSpecialist` (components/specialists.tsx) now returns `{ text, verdict }`. The chat turn stores the verdict, and `VerdictView` in chatconsole.tsx draws one of three views: a gauge (tree models), a ranking (Katyayani) or a timeline (server models). Separately, the 0.2.0 retrain moved the Skandamata numbers (v0 0.790, fused 0.824, fusion weight 0.3) and the Shailaputri NAB numbers (seed 7 at 0.424; five-seed 0.430 [0.394, 0.474]). The cards, PAPER.md, kagglemodels.py and kagglenotebooks.py now match.

## Why

The owner asked for more visible AI. A picture of score against threshold says "how sure" faster than the text does.

## Decisions made

- Verdicts carry only values from the live response; nothing is recomputed in the browser.
- Probabilities are drawn on log-odds clamped at ±14, because Kalaratri scores sit at 0.9997 and above.
- Local testing against the live API needs headless Edge started with `--disable-web-security` and a throwaway `--user-data-dir`, since the API's CORS allows only the site. Kill leftover `--headless` msedge processes first: about 60 had piled up and held the DevTools port, so scripts attached to old instances.

## Next session should

- Chandraghanta Kaggle v12 (NSL-KDD) is still pending, so add its results when it lands.
