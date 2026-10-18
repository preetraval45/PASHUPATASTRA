# NineLevels

- **Date:** 2026-10-18
- **Phase:** Block G — RP-69
- **Commit(s):** this push

## What changed

The training course has nine levels, one per Navadurga form. lib/training.ts
gives each module `level` and `form`; `tier` replaces the old `level` string.
Three new modules: logs-and-detection (Kalaratri), recovery-and-verification
(Mahagauri) and capstone (Siddhidatri, 8 scenario questions). There are 46
questions in total. `levelReached()` returns the highest level reached with
every level below it passed. The Evaluation shows that level as a ladder of
nine.

## Why

The owner asked for cyber-awareness levels based on the nine Durga models.

## Decisions made

- Each form maps to the skill that matches its model's job: Kalaratri covers
  logs, Mahagauri recovery, Katyayani hunting the adversary.
- Facts were checked: Windows event 4624 is a successful logon and 4625 a
  failed one; 4688 is process creation; 7045 is a service install; the 3-2-1
  backup rule.
