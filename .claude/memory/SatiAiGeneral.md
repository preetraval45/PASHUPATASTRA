# SatiAiGeneral

- **Date:** 2026-10-18
- **Phase:** Block G — RP-68
- **Commit(s):** 8938015 (API), this push (web)

## What changed

- `POST /agent/ask` (app/agent/general.py) answers any question. It runs with
  no tools and no estate evidence. The visitor message and the last 6
  exchanges are untrusted Evidence. The schema is general_answer_v1, with
  `area` set to one of the nine Navadurga ids, plus `topic` and `declined`.
- Sati AI's rail is now conversation history, stored in localStorage at
  `pashu.ask.conversations.v1`. The scope picker offers General or an incident.
  General answers render via GeneralTurn and are labelled "general knowledge —
  not from your evidence", with their area.

## Why

The owner asked for chat history in place of the incident list, and for
answers to any cyber or general question.

## Decisions made

- The area is a prompt-level framing. It is never presented as a separate
  trained model, because only Katyayani is trained.
- Until the API is deployed, askGeneral turns a 404 into "needs the latest
  API, not deployed to AWS yet".

## Open questions

- Everything new in the API (/models, /agent/ask, /usage and more) waits on
  the AWS secrets.
