# Auditing the agent, and a cache that never worked

- **Date:** 2026-08-21
- **Phase:** Phase 3 — R22
- **Commit(s):** pending

## What changed

Every chat turn is an `agent_turn` audit record carrying the question, the
answer, the model, the provider, the prompt version and digest, the citations,
and every step taken. The audit page renders it behind "why it said that".

## Decisions made

- **A turn is not an observation.** An observation is something the platform
  saw; a turn is something it said. Filed together, the agent's turns vanish
  into a trail of telemetry.
- **The prompt version carries a digest.** The version is written by hand, so
  it is wrong exactly when someone edited the prompt and forgot to bump it —
  the case a reader most needs to notice.
- **Cached turns are recorded**, with the cost and trace of the run that
  produced the answer. A cache hit is still an answer given to someone.
- **The question is capped and stripped before storage, and kept out of the
  summary.** It is text a stranger typed into a public box, on its way to an
  append-only record on a public page.

## The cache had never worked

R21 made audit refs timestamps. Answering appends an audit record. The refs were
in the cache key. So **the key changed on every request and nothing was ever
served from cache** — invisible, because a cache that always misses still
returns correct answers, just at full price. It is why every session kept
hitting the rate limit.

Two fixes, and the second is the real one:

1. The audit trail left the evidence entirely. It caused three problems with one
   root — *the trail moves while the page does not*: citations that could never
   resolve (the page anchors what existed at render time; the agent cites what
   exists at answer time), a key that changed every request, and the agent
   reading its own previous replies as fact. The plan steps carry the verdicts,
   which is what an analyst actually wanted from it, as refs that stay put.
2. `/health` reports `chat_cache` now. **A cache that fails silently looks
   exactly like one that works.**

Also: the cache resolves its own backend through `backend.durable()` instead of
being handed a store. Being handed one meant it bound on the first question a
container answered and not before, so health could only ever report it unbound.

## Free-tier tuning, measured

`gpt-oss` bills reasoning as output. One factual question: **326 output tokens
at `high`, 43 at `low`** — same answer. These replies summarise evidence already
retrieved and assembled; the reasoning was paid for and thrown away. A live turn
went 6,584 → 4,869 tokens. The provider drops the parameter by itself on an
endpoint that rejects it, so the fallback box needs no special case.

Deployed model is now `openai/gpt-oss-120b` — better, and a separate rate-limit
bucket from the one testing had exhausted.

## The verifier lied a third time

`verifychat.py` read the last answer on the page, so when a question hit the
rate limit and the panel appended an error, the *previous* answer was reported
as that question's — four times over. It now requires the answer count to
increase. Counting what changed, not what is present, is the fix each time.

## Open questions

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**
- Oracle box still unprovisioned; a rate limit is a 429, not a slower answer.

## Next session should

- **R23** — deploy Phase 3 and review. Then stop.
