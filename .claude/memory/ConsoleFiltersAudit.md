# Console filters, audit kind, and the OpenAPI check (RP-53)

**Date:** 2026-10-27

## Why
RP-53 asks for filters across the console. The audit filter had to be server-side: filtering the newest 100 records would let "no approvals" mean "none among the newest 100".

## Decisions
- Filters are link-driven and server-side (`components/filter.tsx`, `lib/incidentfilter.ts`). An unknown value means everything, never an empty list.
- `/audit?kind=` is filtered in all three stores before the limit. DynamoDB now pages until it has enough matches.
- Inline approve/deny stays undone until S4/S5 (sign-in): an anonymous approval would be recorded as a person's.

## Next session
- **Any API route change needs `python -m app.exportopenapi`** in the same commit. CI's contract check failed on fffc775 and silently skipped `deploy api` until 2f38d9c.
- Chandraghanta v1 is recorded as a negative result; Kushmanda's Kaggle workflow is a no-op without GitHub Kaggle secrets (kernels are pushed by hand).
