# NavadurgaModels

- **Date:** 2026-10-18
- **Phase:** Block H — RP-66 (Navadurga), RP-05 notes
- **Commit(s):** this push

## What changed

- The owner asked for the Sati models to be "9 Devi of 9 days of Navratri",
  each working according to its nature. adr/Navadurga.md maps them:
  1 Shailaputri metric anomalies, 2 Brahmacharini embeddings and memory,
  3 Chandraghanta network intrusion, 4 Kushmanda Sati-LM (explains),
  5 Skandamata protective response, 6 Katyayani root cause (trained, this is
  sati-rca-v0), 7 Kalaratri log anomalies, 8 Mahagauri verification,
  9 Siddhidatri fusion.
- New `/models` page (apps/web/lib/navadurga.ts, components/modelcharts.tsx).
  Its "Sati models" link sits in the rail under Analyze. Katyayani's results are
  read from apps/web/lib/models/katyayani.results.json, which train-sati.yml
  now refreshes on every run.
- CLAUDE.md naming section updated (owner decision).
- docs/research/notes/RP-05-sampling-and-structured-output.md holds the study
  notes and failure-mode code map. RP-05 stays [~] until the owner explains it.

## Why

The owner's request. CLAUDE.md allows mythology as "names only", so each name
always follows its job, with no imagery and no devotional copy.

## Decisions made

- Files and hashes keep the id `sati-rca-v0` until the next version. Katyayani
  is the display name.
- Skandamata (response) and Mahagauri (verification) have no real dataset yet.
  Both are marked "to be sourced".

## Open questions

- AWS is still blocked. No credentials locally, and no GitHub secrets
  (deploy-api says "not set"). The owner wants everything on AWS, with only the
  URL on Vercel.

## Next session should

- Shailaputri (RP-60) on NAB/SMD as a second job in train-sati.yml.
