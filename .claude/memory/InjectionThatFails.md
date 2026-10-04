# The injection that fails

- **Date:** 2026-10-04
- **Phase:** Phase 5G — Reachable, then convincing (REBUILD.md R117)
- **Commit(s):** this push; kavach.py, testkavach.py and INC-2026-0904 already
  landed early inside 84a78f6 (an R120 commit, swept in by `git add -A`)

## What changed

INC-2026-0904 is an incident whose evidence argues with the analyst. A failed
scan carries a User-Agent telling the AI to call it an authorised test, close
the incident and run `wipe_host`. `pashupatastra/kavach.py` flags that kind of
text. The model receives it fenced and labelled, the evidence page quotes it as
untrusted, and Dharma denies `wipe_host`.

## Why

"What if your logs tell the AI what to do?" is the first question a security
reviewer asks of an AI responder. The defences existed but could not be seen.
The scenario lets a visitor watch them hold.

## Decisions made

- The tests assume an **obedient** model. The claim is that obeying gets the
  attacker nothing, which has to hold for the worst model, not the best.
- Kavach is a tripwire, not the defence. A paraphrase gets past it, and a
  pinned test says so. Nothing may treat an unflagged line as safe.
- No ATT&CK technique for the injection step: ATT&CK has none, and a wrong
  mapping is worse than none. The text is evidence inside the scanning step.

## Open questions

- Should Sati's answer itself say *this incident contains an attempt to
  instruct me*? Today the flag is in the evidence and on the page. The answer
  wording is left to the model.

## Next session should

- Know that until this push, **every chat answered without the observations'
  text**: `agent/context.py` read only the payload, and the words live in
  `labels.summary`. Live answers may change once deployed. Re-run
  `scripts/verifychat.py` after R122.
- The Blue Team game still lists three scenarios (`testgame.py`). Decide
  whether 0904 belongs in it.
