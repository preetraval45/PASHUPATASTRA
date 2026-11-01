# Direct answers, live incidents, training games

- **Date:** 2026-11-01
- **Phase:** Phase 0 — Foundation (website)
- **Commit(s):** ba98f89, fee20e4, pending

## What changed

- **Sati AI answers:** they state their subject directly and combine models: an explanation brings its defences, and a defence question is searched by its subject (`subject()`, `FRAMING`, `ALIASES` in providers/sati.py).
- **Chat controls:** the chat lost its model and scope dropdowns. The specialist row chooses the model, and an incident chat shows a removable chip instead of the scope dropdown.
- **Incidents:** the page opens on a real live feed (components/happeningnow.tsx). Each incident page has a labelled replay of its audit records (incidentreplay.tsx).
- **Training:** it gains games (lib/games.ts, components/games.tsx), practice flashcards (lib/questionbank.ts) and four learning paths (components/paths.tsx).

## Why

The owner wanted:
- replies that don't talk about "what Sati knows";
- models that choose themselves, and no dropdowns;
- live incidents;
- gamified beginner-to-expert training.

The owner also said that this chat is website-only, with Android in another session.

## Decisions made

- The demo incidents are written scenarios. "Live" therefore means the real public feeds, plus a replay that says it is one, never a scripted incident presented as current.
- Mitigation order for an explanation comes from the phrasing "How do we defend against <title>?". That phrasing put User Training first for phishing.
- Another session edits apps/android with uncommitted files. Always use `git pull --rebase --autostash`, and stage only `apps/web`, `services/api`, `docs` and `.claude/memory`.
- ba98f89 shipped a TS error (`flatMap` needed `<ReactNode>`), and fee20e4 fixed it. Run `npx tsc --noEmit` after every change to `answertext.tsx`.

## Next session should

- Check the live chat after the API deploy: "How do we defend against ransomware?" should name T1486 with Data Backup.
