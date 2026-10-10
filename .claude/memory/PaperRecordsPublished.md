# The paper's records published, and a page that noticed by itself

- **Date:** 2026-10-09
- **Phase:** Phase 5G — Reachable, then convincing
- **Commit(s):** `bcc5849`, plus the regeneration that followed it

## What changed

`docs/research/experiments/` and the paper's `.docx`/`.pdf` are in the
repository. Six JSON record files, 212 kB, behind RQ2–RQ4: the policy run over
all 104 PIB scenarios in three contexts, the compromised-model run, and the
indirect-injection sweep against three local models. `/evaluation` now reports
those figures as recomputable, and still reports the cluster benchmark's arm
numbers as not.

## Why

The owner asked for everything to be committed. The records had been written
two days earlier by a parallel session and deliberately left untracked, because
publishing someone's experimental data is the owner's call and not a session's.

## Decisions made

- **The `.docx` and `.pdf` are in, with the cost stated.** They are binaries in
  a repository that keeps its prose in Markdown: they do not diff and they will
  drift from `PAPER.md`. Committed anyway, because a reader checking a table
  should not have to rebuild the document to find it. If they start
  contradicting `PAPER.md`, that is the moment to drop them.
- **Scanned before committing**, since these are raw chat transcripts of
  injection attempts and gitleaks runs over full history in CI. No tokens, keys
  or addresses.

## The thing worth remembering

`scripts/buildevaluation.py` said the records were recomputable **without being
edited**, because `tracked_records()` asks `git ls-files` rather than the
filesystem. That function originally checked whether the files existed on disk,
which would have reported untracked working-tree files as published — a false
claim in the direction that flatters the project, on the one page whose subject
is what this project cannot yet prove.

The general rule, and it has now paid off twice: **a generated page must derive
its claims from the same authority a reader would check.** A reader verifying
"these records are in the repository" runs `git ls-files`, so the generator has
to as well. Asking the filesystem was asking a different question that usually
gives the same answer.

## Open questions

- **The deploy is still the binding constraint.** Nothing has shipped to
  pashupatastra.vercel.app since the Vercel Git integration was disconnected —
  `/evaluation` 404s in production and none of R124–R128 is publicly visible.
  It needs `VERCEL_TOKEN`, `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` as GitHub
  repository secrets; the `deploy site` job is written and waiting on them.
  `vercel.json` also carries `"git": {"deploymentEnabled": false}` in both
  copies, so reconnecting the integration alone would not deploy either.
- **`benchmark/results/` is still gitignored and all six declared arms still
  have zero recorded runs here.** Table VII of the paper cannot be recomputed
  from this repository, and the page says so.
- **Diagnosis accuracy is still unmeasured.** The grader exists
  (`pashupatastra/diagnosis.py`, 60-way choice, 1.7% baseline) and has never
  graded anything, because the only legitimate input is injected telemetry and
  no cluster has been stood up. Docker Desktop is installed but not running and
  Kubernetes is not enabled on it.

## Next session should

- Check whether the three Vercel secrets were added; if so, confirm
  `/evaluation` answers 200 in production and run `verifysite.py`,
  `verifydefang.py` and `verifyevaluation.py` against the deployed site, which
  is what R115 and R121 have been waiting on.
- If a cluster appears, the diagnosis run is the highest-value experiment left:
  it closes the venue review's largest finding and the instrument is already
  written and tested.
