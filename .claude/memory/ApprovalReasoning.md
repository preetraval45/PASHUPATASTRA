# The tier explains itself, or nothing does

- **Date:** 2026-08-25
- **Phase:** Phase 5B — Satisfying to operate (R65)
- **Commit(s):** pending

## What changed

`Verdict` carries `tier_reasons`: one `TierStep` per rule that fired while the
tier was being decided — the risk band first, then each hard override, each with
`from_tier`, `to_tier`, the factor it prices, and a detail string built from the
numbers that branch tested. `RiskAdjustment` gained the same `factor` tag.
`evaluate` no longer assigns to a local `tier`; it moves a small `_Ladder`
object that records every move. The approval panel draws the four-step autonomy
scale (order and bands from `/policy/model`), marks where the action landed and
where its score alone would have put it, and lists the steps verbatim.

## Why

The old panel showed the arithmetic and the tier, and the arithmetic is the
wrong explanation for the interesting cases. `force_password_reset` scores 20 —
autonomous — and is denied because it cannot be undone. A red badge beside a 20
reads as a bug in the arithmetic, which is the opposite of what an approval
surface is for: the operator has to be able to say *why* it needed approving.

The obvious fix — hand the panel the numbers and let it restate the rules — is a
second implementation of the policy. The engine emits the sentences instead.

## Decisions made

- **The ladder is a class, not a local variable** — so changing the tier without
  recording why is not something `evaluate` can express. Rules this out: an
  explanation assembled afterwards from the same conditions, which is two
  implementations of one decision that agree only until someone edits one.
- **A rule that fires without moving the tier is recorded as *held*, not
  dropped.** `delete_infrastructure` is already denied by its score when the
  irreversibility rule reaches it; listing only movements would explain that
  denial as a high number when the real reason is that there is no way back.
- **`tier_reasons` is optional on the wire** (`default_factory=list`). A client
  that has not been redeployed still posts older verdicts back to
  `/policy/approve`; 422-ing them would break approval exactly during a rollout.
  Cost: FastAPI now splits the contract into `Verdict-Input`/`Verdict-Output`.
  Nothing generates clients from `openapi.json`, so this is churn, not a break.
- **The scale's order and bands come from `/policy/model`**, not from four cells
  typed into the component — same reasoning as R54.
- **Colour is never the only signal.** `▲` is shared by senior and denied, so
  position, name, marker and border weight carry the state, and the checker
  measures that through a grayscale filter rather than reading class names.

## Open questions

- `openapi.json` was **already stale on `main` before this change** — the
  committed spec disagreed with what the current exporter produces. It has been
  regenerated here, so the diff is large and mostly not R65. Worth confirming
  the CI `--check` step is actually green on `main`, since a check that has been
  failing for four commits is a check nobody is reading.
- The `no_tested_rollback` branch is unreachable from the registry (every
  registered action has a rollback, is irreversible, or changes nothing), so its
  test builds an `ActionSpec` by hand. If that stays true, the branch is
  guarding future registry entries only.

## Next session should

- R66 — keyboard triage (`j`/`k`, `Enter`, `?`), then R67 to deploy 5B and
  review. `verifyapproval.py` defaults to the deployed site and API, so it runs
  as-is once the Lambda carries `tier_reasons`; until then pass `--site`/`--api`
  to point it at a local pair.
