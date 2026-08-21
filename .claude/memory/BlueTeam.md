# Blue team mode, and two ways to build an unwinnable game

- **Date:** 2026-08-21
- **Phase:** Phase 4 — R27
- **Commit(s):** pending

## What changed

`/blue-team` — the incident played forwards. One alert, the player investigates,
commits to an explanation and a response, and is marked out of 100. All three
scenarios verified playable and scored in a browser against the deployed site.

## Decisions made

- **The answer stays on the server.** The briefing has no confidence, no
  contradictions, no chain, no technique mapping, no plan. A page that ships its
  own solution teaches the player to open dev tools.
- **Three scoring dimensions, because incidents fail on three.** Right cause +
  sledgehammer. Proportionate action for the wrong reason. Right by luck, never
  having opened the evidence that kills the plausible alternative — which is the
  one this is really for.
- **Candidates are hash-ordered.** Source order puts the correct explanation
  first every time; random order moves options under a player who reloads.
- **The reveal shows what ruled the decoy out**, with links to those events.
  Being told the right answer teaches less than being shown the specific
  observation that killed the answer you were drawn to.

## Two bugs of the same kind: looks fine, cannot be won

1. **The action menu was the registry sorted by risk, first eight.** That left
   `isolate_host` off the menu for a beaconing workstation, so the response
   dimension could not score above a third. Nothing failed; it was just
   impossible. A menu has to contain the right answer to test anything.
2. **Excluding rollbacks by "appears as some action's `rollback_action_id`"
   removed every correct answer.** The relationship is *mutual* —
   `isolate_host` ↔ `rejoin_network` each name the other — so that predicate
   matches both halves of every reversible pair. There is no direction to read
   from the registry. The only precise exclusion is the inverse of *this*
   incident's plan.

## The checker must not know the answers

The first `verifyblueteam.py` guessed: it picked the last option and called that
the careful attempt, then reported two scenarios broken because its guess was
the decoy. **It was measuring itself.**

It now submits *every* explanation and asserts exactly one scores the diagnosis
marks, and isolates investigation by changing only whether evidence was opened.
Both are checkable from outside with no second copy of the truth to drift.

That is the fourth time this session a green or red check meant nothing. The
pattern each time: assert on what *changed* between two runs, not on a value the
checker believes it knows.

## Open questions

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**
- `host:app-07` yields no events — the evidence sits on
  `process:app-07/schtasks`. Left as-is: an analyst checking a host and finding
  nothing is the real experience, not a broken button.

## Next session should

- **R28** — a streak or score that persists, DynamoDB-backed, anonymous by
  default. A leaderboard that collects names is a personal-data decision, not a
  feature decision.
- Then **R29**, the final Phase 4 deploy and pass.
