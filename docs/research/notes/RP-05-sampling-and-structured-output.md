# RP-05 — Sampling and structured output

Study notes and a code map prepared for the owner's RP-05 learning task. The
task is done when **you** can explain the last section in your own words, so
this file is something to read and then argue with, not the answer itself.

## 1. How a model picks the next token

A language model outputs a score (a *logit*) for every token in its
vocabulary. Softmax turns those scores into probabilities. Sampling decides
which token to use.

| Setting | What it does | Effect |
|---|---|---|
| **Greedy** | always take the most probable token | deterministic in principle; can loop or repeat |
| **Temperature T** | divide the logits by T before softmax | T < 1 sharpens toward the top token, T > 1 flattens toward randomness, T → 0 approaches greedy |
| **Top-k** | sample only from the k most probable tokens | removes the long tail of nonsense |
| **Top-p (nucleus)** | sample from the smallest set whose probabilities add up to p | adapts to how confident the model is |

Pashupatastra calls every model at **`temperature: 0`**
([openaicompat.py:178](../../../services/api/app/engines/providers/openaicompat.py),
and again at line 234). Diagnosis should not depend on luck.

## 2. Why temperature 0 is still not perfectly deterministic

Temperature 0 means "take the highest logit". But the logits themselves can
differ by a tiny amount from one run to the next:

1. **Floating point is not associative.** `(a + b) + c` and `a + (b + c)` can
   differ in the last bits. A GPU sums thousands of numbers in parallel, and
   the order of those additions depends on how the work is split across
   threads.
2. **Batching changes the split.** On a shared server, your request is batched
   with other people's requests. A different batch size can mean a different
   kernel, a different reduction order, and so different last bits.
3. **Near-ties flip.** When two tokens have almost equal logits, a difference
   in the last bit changes which one is "highest". After one different token,
   everything after it can diverge.

So temperature 0 gives a near-deterministic answer, not a guaranteed one.
That's why the benchmark runs N = 3 and reports instability, rather than
assuming one run is the answer.

## 3. Structured output — asking for a schema, not prose

Rule 4 in CLAUDE.md says model calls return validated schemas. There are two
layers:

- **Asking:** the request sends `response_format: {type: "json_schema",
  strict: true, schema}` ([openaicompat.py:168-176](../../../services/api/app/engines/providers/openaicompat.py)).
  Providers that support it constrain decoding to the schema.
- **Checking anyway:** the reply is parsed and validated, and anything that is
  not a JSON object raises `SchemaViolation`. A provider's promise is not
  evidence.

## 4. Where each failure mode is handled

| Failure | What happens | Where |
|---|---|---|
| Transport error, rate limit, timeout | `ProviderUnavailable`; retried with backoff; trips the circuit breaker | [openaicompat.py:109-142](../../../services/api/app/engines/providers/openaicompat.py), [gateway.py:410-418](../../../packages/core/pashupatastra/gateway.py) |
| Circuit open after repeated failures | refuses to call and says "escalate instead" | [gateway.py:401-405](../../../packages/core/pashupatastra/gateway.py) |
| Invalid JSON, or JSON that is not an object | `SchemaViolation`; retried, but does **not** trip the breaker, because a bad schema shouldn't take a healthy provider offline | [openaicompat.py:184-190](../../../services/api/app/engines/providers/openaicompat.py), [gateway.py:419-424](../../../packages/core/pashupatastra/gateway.py), [gateway.py:735-741](../../../packages/core/pashupatastra/gateway.py) |
| Empty answer on the final hop | `SchemaViolation("provider returned no content on the answering hop")` | [gateway.py:735](../../../packages/core/pashupatastra/gateway.py) |
| Out of token budget mid-conversation | stops; trace entry `budget_exhausted`; answer marked `truncated` | [gateway.py:498-508](../../../packages/core/pashupatastra/gateway.py) |
| Model asks for a tool it wasn't offered | not executed; trace entry `refusal` | [gateway.py:600-605](../../../packages/core/pashupatastra/gateway.py) |
| Answer cites evidence that was never retrieved | the citation is dropped and counted; an answer with nothing left is withheld | `app/agent/chat.py` (`dropped_refs`) |

## 5. Why this matters for Sati-LM

Sati-LM (RP-65) will be our own decoder. Unlike a hosted API, we control its
decoding loop. *Constrained decoding* means masking every token the schema's
grammar does not allow at each step. Then an invalid JSON answer is impossible
by construction, rather than caught after the fact. Section 2 is why its
evaluation still runs more than once.

## Check yourself (the done-when)

- Why does `temperature: 0` still not guarantee identical output on a GPU?
- Why does a `SchemaViolation` not trip the circuit breaker, while a
  `ProviderUnavailable` does?
- With constrained decoding, which row of the table in section 4 disappears?
