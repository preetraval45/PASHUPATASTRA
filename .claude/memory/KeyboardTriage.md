# The help sheet is the source, not a copy of one

- **Date:** 2026-08-25
- **Phase:** Phase 5B — Satisfying to operate (R66)
- **Commit(s):** pending

## What changed

`components/keys.tsx`: `isTypingIn` (the one implementation of "is somebody
typing", now used by `/`, `?` and `j`/`k`), `aDialogIsOpen`, a shortcut registry
context, and the `?` sheet. `components/triage.tsx`: `TriageList`/`TriageItem`,
which give the incident list `j`/`k`/`Enter` with an explicit index per card.
The footer gained a "Keyboard shortcuts ?" button. `scripts/verifykeys.py` and
a `--press` option on `verifycontrast.py`.

## Why

The site already had two undocumented shortcuts (`/` since R15, `Ctrl-K` since
R60). Adding two more without a discoverable list would have made the keyboard
surface a thing you had to read the source to find — and a list typed out by
hand goes stale the first time a shortcut moves.

## Decisions made

- **The sheet is assembled from a registry**, so it lists what the mounted page
  actually binds. Rules out telling a reader on the audit page that `j` moves to
  the next incident, which is worse than saying nothing.
- **`mouse` is a required field on every shortcut row**, not a nicety. The
  requirement was "every one of them has a mouse equivalent"; making it a field
  the type demands is how that stays true after the next one is added.
- **Order comes from the page as an explicit `index` prop**, not from mount
  order. React does not promise mount order matches document order.
- **Not wired to the overview's compact incident list.** Each row there is one
  link that Tab already reaches; `j`/`k` would duplicate a working key.
- **`Ctrl-K` deliberately still fires inside text fields** — nothing native
  happens there, so it costs nobody a keystroke. Only single-letter shortcuts
  defer. The palette's comment had claimed a guard it did not have; corrected.

## Open questions

- The repo is not Prettier-clean at any print width — running `prettier --write`
  on an existing file produces a large unrelated diff. Formatting was matched by
  hand here. Worth deciding whether to adopt a config and reformat once, or to
  keep hand-formatting; the current state is a trap for the next session.
- `openapi.json` staleness from R65 is still worth confirming against CI.

## Next session should

- R67 — deploy Phase 5B and review. `verifykeys.py` and `verifyapproval.py` both
  default to the deployed site; run them there once the Lambda and Vercel carry
  this branch. Note `verifykeys.py` needs at least three incidents on
  `/incidents` to exercise moving between them.
