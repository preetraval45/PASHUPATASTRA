# /findings page

- **Date:** 2026-10-26
- **Phase:** Block G — Product
- **Commit(s):** pending

## What changed

A new public page, `apps/web/app/(site)/findings`, under Learn in the
sidebar and in the command palette. It shows six findings:

- split leakage on CIC-IDS2017;
- the sim-to-real gap;
- Shailaputri on SMD (quieter and more accurate);
- Kushmanda answering from evidence;
- the negative results (Mahagauri, Siddhidatri);
- the false-alarm metric bug.

## Why

The owner wants the site to be compelling and to serve as O-1 evidence. The
headline results were spread across model pages, and negative results
deserve the same space as positive ones.

## Decisions made

- **No typed numbers.** Every number is read from the committed results JSON,
  so the page cannot drift from the evidence. The metric-bug card is the only
  card with no number.

## Next session should

- When results files change shape, `npx tsc` catches mismatches here.
