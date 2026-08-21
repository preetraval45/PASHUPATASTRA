# Sati proposes, Dharma authorises

- **Date:** 2026-08-21
- **Phase:** Phase 3 — R20
- **Commit(s):** pending

## What changed

The chat agent can now name an action, and naming it routes it through the
existing policy engine into the existing approval queue. Live: asking the
deployed console to isolate a host returns `isolate_host`, a verdict of `senior`
at risk 67 requiring a `senior_operator`, an approval id, and an audit line.
Nothing executed.

## The correction that matters

The first version passed `agent_risk_limit=0` to `evaluate`. It reads as the
cautious choice. It forces `Tier.DENIED`, and `/policy/approve` refuses a denied
verdict — so **every proposal dead-ended exactly where R20 wants it to reach a
human.** Verified live before it was noticed: the deployed console returned
`denied at risk 67`.

`agent_risk_limit` answers *may this agent act alone* — always no here. Using it
to answer *may a human approve this* conflates two different questions. The fix
was to drop it: proposals are scored exactly as a person's request is, which is
also the plainest reading of "no weaker path for AI-initiated actions than for
human ones" — it is the *same* path.

**What actually stops the agent acting is structural, not a risk number.** The
route has no execute path, and no risk-bearing action is in the tool set. A
number would have been a setting someone could change.

## Decisions made

- **Two locks, both required.** `ActionSpec.read_only` says a thing is a read;
  `AgentSpec.may_use` says this agent was given it. Marking something read-only
  by mistake does not reach a public text box on its own.
- **Proposed ids are validated against the registry** — the same discipline as
  citations. A model naming `quarantine_host` (plausible, not an action here)
  would otherwise queue an approval for something that cannot be executed,
  reviewed or rolled back.
- **Proposals are never cached.** A cached copy would answer "queued for
  approval" without queueing anything — a lie the second visitor cannot detect.
- **`AgentSpec` reused rather than reinvented.** It already carried `risk_limit`
  and `may_use`, and `may_use` already stated the rule this depends on: a tool
  absent from the declaration is unreachable, not discouraged.

## Open questions

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**
- Oracle box still not provisioned, so a rate limit is a 429 rather than a
  slower answer. `scripts/oracle-ollama.sh` is ready.
- Still unanswered: `logo.png` or the square spear for the Google Search icon?

## Next session should

- **R21** — the chat panel UI. Everything behind it works and none of it is
  visible on the site yet.
- Then R22, which writes the model id, prompt version and full tool-call trace
  to the audit table for every turn.
