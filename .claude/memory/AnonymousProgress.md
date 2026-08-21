# A streak, deliberately not a leaderboard

- **Date:** 2026-08-21
- **Phase:** Phase 4 — R28
- **Commit(s):** pending

## What changed

Blue team scores persist between visits, keyed to an opaque token the browser
generates. Verified twice: a new browser context carrying only the token read
the record back, and the record survived a forced replacement of every Lambda
container (`durable: true`).

## Why a streak and not a leaderboard

A leaderboard with names is a system that collects names. It needs a retention
answer, a deletion path, a moderation policy for what people type into it, and a
line in a privacy notice. None of that is worth acquiring so a training exercise
can say "well done".

## Four things that make "anonymous" a property, not a promise

- **The token is validated to a UUID shape.** Without it the identifier is an
  arbitrary string that becomes a DynamoDB sort key — it would store
  `alice@example.com` the first time anyone sent one.
- **No route lists players.** The absence is the feature: an enumerable set of
  scores *is* a leaderboard. A token reads only itself.
- **The token is not in the audit line.** The trail is public, and a
  pseudonymous id beside a timestamp on a public page can be correlated.
- **The page never mints one.** `readPlayer` on render, `ensurePlayer` on
  submit. A first-time visitor sees no mention of tokens, storage or streaks.

Clearing the token *is* the deletion path — with nothing to join them to, the
orphaned rows are not a record of anybody.

## Scoring rules worth keeping

- The score is computed server-side and never accepted from the client. A number
  a player can choose is not a score; a test asserts the request model has no
  field resembling a total.
- Best per scenario is a **maximum**, not the last result. A player who scores
  100 and then experiments with a wrong answer has not got worse at it.
- The streak breaks below `sound` (70). A streak that survives a wrong diagnosis
  measures persistence, not competence.
- `record()` is pure and folds previous state, so the rules are testable without
  a store and the durable and in-memory paths share them.

## Consistency with earlier phases

`Progress` resolves its backend through `backend.durable()` on each access
rather than being handed a store — the same correction the answer cache needed
in R22, where being handed one meant it bound on the first request a container
served and `/health` could only ever report it unbound.

## Open questions

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**

## Next session should

- **R29** — the final Phase 4 deploy and pass. Everything it depends on (R25,
  R26, R28) is done.
