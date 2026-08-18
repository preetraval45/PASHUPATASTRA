# ADR — Smriti retrieval: hybrid, and why the basis is reported

**Status:** Accepted · 17 August 2026
**Planned in:** [README.md](README.md) — "Smriti retrieval — embeddings vs. hybrid"
**Evidence:** 30 tests in `packages/core/tests/testsmriti.py`, 9 integration tests
in `testreasoning.py`

## Context

Smriti answers "have we seen this before?" — the first question an experienced
operator asks, and the one a new system cannot answer at all. The roadmap left
the retrieval method open: pure embeddings, or embeddings plus structured
filters.

The choice looks like an accuracy trade-off. It is not. It is a decision about
what kind of *claim* the system is allowed to make.

## The problem with pure vector retrieval

Embeddings rank by textual resemblance. Two incidents described as "connection
pool exhausted" score highly against each other whether they are:

- the same service failing the same way twice — a real precedent; or
- two unrelated services that happen to share a phrase.

**Nothing in the prose distinguishes those cases**, so no embedding model can
separate them, and a better model does not help. What separates them is
structure: the entity involved and the signal that fired. That information exists
in the incident record and is simply not in the sentence.

The failure this produces is specific and bad. The system says "this resembles
INC-2026-0042", the operator reads it as *we have seen this before*, and spends
the first twenty minutes of an outage investigating a service that has nothing to
do with it — with more confidence than if the system had said nothing, because
the recollection carried the authority of history.

## Decision

### 1. Hybrid retrieval, with structure as more than a tiebreaker

Every match is classified by **why** it matched:

| Basis | Meaning | Counts as precedent |
|---|---|---|
| `SAME_ENTITY` | The same entity failed before | Yes — strongest |
| `SAME_SIGNAL` | The same failure mode, elsewhere | Yes — a *different* claim |
| `TEXT_ONLY` | Reads similar, shares no structure | **No** |

Ranking is **within** a basis, never across it: the weights are separated far
enough that a strong text-only match cannot outrank a weak same-entity one. A
single blended relevance score would let a coincidence of phrasing win on a good
enough embedding, which is the exact failure above.

`recall()` returns everything with its basis attached; `precedents()` returns only
the matches that justify the phrase "we have seen this before". The UI and the
reasoning layer use the second, so a text-only resemblance cannot be presented as
history by accident.

### 2. The asymmetry that makes it hybrid rather than filtered

A **text-only** match must clear a similarity floor on its own. A **structural**
match does not — shared structure is itself evidence of relatedness, so a prior
incident on the same service surfaces even when the wording has nothing in common.

This is the part a filter-then-rank design gets wrong: filtering by entity and
*then* ranking by similarity discards the case where the same service failed
before and nobody described it the same way. That is a common case, and often the
most useful one.

### 3. The default embedder is local, lexical, and honest about it

`HashingEmbedder` — a hashing vectorizer over token unigrams and bigrams — ships
as the default. It is a real technique, not a stub, and it captures lexical
overlap. It does **not** capture meaning: "pool exhausted" and "no free
connections" describe one failure and will not match.

That limitation is deliberate. Because the default is lexical, the structured
filters carry most of the weight, so retrieval degrades *honestly* when no hosted
embedder is configured rather than appearing to work and quietly missing things.
`packages/core` keeps running on a laptop with no credentials (the Platform ADR),
and a hosted embedder plugs in behind the `Embedder` protocol without changing a
line of calling code.

Adopting one should be a measurement, not an assumption — `score_retrieval`
exists so the upgrade can be justified the way the graph store was.

### 4. The outcome travels with the recollection

A recalled incident is useless — worse than useless — without what happened to
it. `Outcome.warning` makes three cases loud:

- the prior diagnosis was later found **wrong**
- the remediation **failed verification**
- the incident was **never resolved**

A wrong prior diagnosis is the most valuable thing memory can tell you and the
first thing a naive implementation drops. Surfacing "this resembles INC-42"
without saying INC-42 was misdiagnosed lends the authority of history to a
mistake, and the operator inherits it with more confidence than the person who
originally made it. The warning is injected into the evidence the model sees, not
only into the UI.

### 5. Ingested documents arrive untrusted, and there is no shortcut

`ingest_document` has **no `trust=` parameter**. A runbook is a document that
anyone with repository access can edit, and a parameter is something a person
passes `VERIFIED` to while wiring up an importer at 2am. The only route to
trusted is `promote()`, which requires a named actor and records them as owner.

### 6. Tenant isolation is structural

`tenant` is a required positional argument on every read, and there is no method
that reads across tenants. An unknown tenant returns an empty list rather than an
error, so the API cannot be used to enumerate which tenants exist.

## Consequences

**Good.** The system can distinguish "this happened here before" from "this reads
like something that happened somewhere" — and say which. Recollections carry
their outcomes, so history informs rather than anchors. Memory runs with no
credentials, so it is exercised by the ordinary test suite rather than only in an
environment that can spend money.

**Costs.** The lexical default will miss semantically-similar incidents that share
no vocabulary. That is a real recall gap, accepted knowingly, and it is the
argument for a hosted embedder later — to be made with `score_retrieval` numbers
rather than intuition.

Storage is in-memory. The interface is what matters here; the persistence decision
is deferred, and should be settled by measurement the way [Graph](Graph.md) was.

**Owed.** Recall measured on real incident pairs. `score_retrieval` reports
`false_precedents` separately from misses on purpose — a missed precedent costs an
operator time they would have spent anyway, while a false one sends them
confidently down a path that does not exist, and the two must never be averaged
into one number.

## Alternatives rejected

**Pure vector retrieval.** Cannot distinguish a precedent from a coincidence of
vocabulary, because the distinguishing information is not in the text. No
embedding model fixes this.

**Filter by entity, then rank by similarity.** Loses the case where the same
service failed before and nobody wrote about it the same way — common, and often
the most useful recollection available.

**One blended relevance score.** Simpler, and it silently permits a strong
text-only match to outrank a real precedent. The basis is not a diagnostic detail
to be collapsed into a number; it is the difference between two different claims.

**Requiring an outcome before storing.** Rejected: outcomes are usually known much
later than incidents, and forcing one would mean either blocking the write or
defaulting to "resolved" — the second of which would fabricate the most
consequential field in the record.
