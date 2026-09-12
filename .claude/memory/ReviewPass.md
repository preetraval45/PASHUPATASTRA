# The review pass — two outside reviews, an O-1 map, and a site that was timing out

- **Date:** 2026-09-12
- **Phase:** Phase 5E — What two reviewers hit; Phase 5F — Evidence
- **Commit(s):** 2d9a6b2 (R71–R73 landed) through 9bb30ee (R111); pending push

## What changed

Two outside reviews of the deployed site and an O-1A strategy document were
folded into `docs/REBUILD.md` as Phases 5E (R93, R98–R106) and 5F
(R107–R113), and a new `docs/O1 visa roadmap.md` maps the eight criteria to the
tasks that produce evidence and to the decisions only the owner can make.

Then most of 5E: R93 (`/policy/preview`, a read no longer writes), R98 (audit
runs fold to `×N`), R101 (typed failures, one retry, per-attempt timeout),
R102 (one resolver for "decisive", the debrief sentence agrees with the
score), R103 (uncited prose is withheld; a ten-case adversarial battery shared
by the deterministic suite and the live checker; CI runs the API suite in the
deployed configuration so those tests stop skipping), R104 (`/usage` from the
ledger), R105 (`86% stated`), and the code halves of R99 and R100. From 5F:
R108 (`CITATION.cff`, generated cite block, no DOI yet) and R111 (README).

## Why

**The 503 was found, and it was worse than the reviewers saw.**
`recent_events` read every feed event ever stored and sorted it in Python;
the layout called it through `/search/index` on every route. On 12 September
that read took 5–30 s and API Gateway cut it at 30 s with a 503. Measured with
`scripts/verify503.py`: `/intel` at 4.9 s, 7.8 s, 20.9 s, then 503 at 30.09 s;
every page on the deployed site at **12–30 s to first byte**. Not a cold start
— `/incidents/{id}` answered in 112 ms on the same container. The fix is a
per-source recent-events index maintained on write (no new GSI: the free
tier's capacity is already spent), `snapshot` querying per node, a `warm`
task, and a 5 s no-retry cap on the layout's index fetch so a page never waits
on a palette again.

## Decisions made

- **REBUILD.md stays the one plan; the O-1 file is a map, not a plan** —
  every script, memory file and "do R7" depends on one numbering.
- **A preview verdict cannot be approved** — it carries a `preview`
  constraint and `/policy/approve` returns 409, so a verdict nobody recorded
  cannot become an approval with no evaluation before it.
- **Withheld, not warned** — answerable prose with zero resolving refs is
  replaced by one sentence; the text goes to the ledger as `withheld_answer`
  and is excluded from the response model so no client can render it.
- **Cached turns are turns, not tokens** in `/usage`; a cached record carries
  the producing run's count (R22).
- **The audit fold is consecutive-only** and the 143 stale records are kept;
  the first deletion from an append-only ledger is a precedent not worth
  setting for tidiness.
- **Web tests exist now**: Node 24 runs `.ts` directly, so `npm test` is
  `node --test lib/*.test.ts` with no dependency; CI runs it.
- **`CITATION.cff` carries version 0.1.0** — the package's, because there are
  no releases and a number typed to look like one is an invented figure.

## Open questions

- Whether the recent index's one-time rebuild (a full read on first call
  after deploy) fits inside the 30 s limit today. If not, the `warm` task
  should be invoked once by hand right after the deploy so the rebuild
  happens off the request path.
- Ruff 0.16 locally reports ~29 findings on the committed HEAD that CI's
  pinned version does not; not touched, not this session's.

## Next session should

1. **Deploy the API** (`scripts/buildlambda.py`, `scripts/deploylambda.py`)
   with credentials — this session had none — then create the warm schedule:
   `python scripts/schedulefeeds.py --task warm --name pashupatastra-warm
   --rate "5 minutes"`.
2. Run `scripts/verify503.py` twice an hour apart (R99), `verifyagent.py`
   for the live battery (R103), `verifydebrief.py` (R102), `verifyusage.py
   --page` (R104), and the Phase 5C page halves (R74) — that is R106.
3. Then Phase 5F: R107 `/impact`, R109 `/press`, R110 the study mode.
4. Owner decisions still blocking: licence (→ Zenodo, R108), domain (R112),
   which paper, study recruitment.
