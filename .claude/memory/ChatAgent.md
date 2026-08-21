# The chat agent, on free model providers

- **Date:** 2026-08-21
- **Phase:** Phase 3 — R19
- **Commit(s):** pending

## What changed

`POST /api/v1/agent/chat` answers questions about one incident, grounded in the
store, with the tool-call trace recorded. Live on the deployed API.

## Why this shape

The owner ruled out Anthropic and any pay-per-token model. Because every model
call already went through the AI Gateway (rule 5), that was configuration rather
than a rewrite — which is the clearest payoff that rule has produced so far.

- **Groq free tier** primary: `openai/gpt-oss-20b`, ~2s a turn, 8,000 tokens/min,
  1,000 requests/day, no expiry.
- **Ollama on Oracle Always Free** fallback: 4 ARM CPUs, 24 GB, no quota, slow.
  Chosen for how the limits *differ* — Groq fails under a burst, the box is too
  slow to lead. `scripts/oracle-ollama.sh` provisions it behind HTTPS + a bearer
  token; an open LLM endpoint gets found by scanners in days.
- **Not AWS, for this one piece.** Ollama needs 3–4 GB; the AWS free tier is a
  1 GB instance and a usable one is ~$30/month. Oracle's free shape is 24 GB.

`openai-compat` is one provider class for Groq, Ollama, vLLM and OpenRouter —
they all speak chat-completions, so the vendor is a base URL.

## Decisions made

- **Retrieval is deterministic; tools fetch only *more*.** If grounding depended
  on the model choosing to retrieve, then it choosing not to would produce an
  ungrounded answer indistinguishable from a grounded one. It also means the
  fallback's small model, which has no tool support, still answers.
- **Citations are verified against what was actually retrieved.** Exact match.
  Unmatched refs are dropped into `dropped_refs` and the turn reports
  `grounded: false`. A cited source nobody checks is decoration.
- **The visitor's message is untrusted**, fenced like evidence, never in the
  instruction channel. It feels like the trusted half because it is the reason
  the call happens — which is what makes that a one-line mistake.
- **`read_only` is declared on `ActionSpec`, not inferred from risk.**
  `changes_nothing` is true of `notify_analyst`, which pages a human. The two
  are opposites: one widens unattended execution, the other narrows what a model
  may touch.
- **Reasoning and formatting are separate calls.** A hop offering tools cannot
  also demand strict JSON — the model must be free to emit a tool call — so the
  structured answer is requested once it stops reaching for tools.
- **Answers are cached durably**, keyed on incident + question + model +
  instructions + evidence. Repeats cost nothing; verified at 0.01s across
  separate Lambda invocations, which only works because R18 landed first.

## Things that bit, worth not repeating

- **`max_tokens` defaults to 16,000** in the gateway. Providers count
  `prompt + max_tokens` against the rate limit, so a 640-token question asked
  for 17,938 and was refused — a failure that reads like "context too big" when
  it was the reservation. `chat_answer_tokens` is 800.
- **urllib's User-Agent is blocked by Cloudflare** (error 1010). Groq answered
  403 before the request reached the API, which looks exactly like a bad key.
- **`incident.event_ids` is empty on the demo incidents** — every event
  reference lives on a causal-chain step. Reading only the former produced a
  context with no telemetry, and nothing failed, because an incident summary
  reads fine without it. The answers were just thinner than they looked.
- **The provider's error body was being returned to the public**, including the
  Groq organisation id and a billing link. Now logged, with a plain 429.

## Open questions

- The Groq key was pasted into a chat window on 21 August 2026. **Rotate it.**
- Oracle box is not provisioned yet, so there is no fallback and a rate limit is
  still a 429 rather than a slower answer.
- Still unanswered: `logo.png` or the square spear for the Google Search icon?

## Next session should

- Finish **R20**: asking the agent to isolate a host should produce a *pending
  approval record*, not only an explanation. Everything else in R20 is done.
- Then **R21**, the chat panel UI, which is what makes any of this visible.
