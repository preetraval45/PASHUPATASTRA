"""Smriti — organizational memory.

"Have we seen this before?" is the first question an experienced operator asks
and the one a new system cannot answer at all. This module answers it, and the
way it can go wrong is worse than the problem it solves.

**The outcome is the valuable half.** A similar prior incident is only useful
alongside what happened to it. Surfacing "this resembles INC-2026-0042" without
saying that INC-2026-0042 was *misdiagnosed* actively hurts: it lends the weight
of history to a wrong answer, and the operator inherits the earlier mistake with
more confidence than the person who originally made it. So a recollection always
carries its outcome, and a wrong prior diagnosis is surfaced as a warning rather
than quietly omitted.

**Retrieval is hybrid, and the structure is not a tiebreaker.** Pure vector
search returns text that *reads* similar. Two incidents both described as
"connection pool exhausted" may share nothing but a phrase — different services,
different clusters, no relationship at all. Embeddings cannot tell those apart,
because the thing that distinguishes them is not in the prose. So matches are
classified by *why* they matched (see `MatchBasis`), and a text-only resemblance
is surfaced as a weaker, differently-worded claim rather than being ranked
alongside a match on the same entity. See `docs/adr/Smriti.md`.

**Nothing is recalled that was not stored.** An unmatched query returns nothing
and says so. A memory layer that produces a plausible-sounding precedent when it
has none is the same failure as an uncited hypothesis, one layer down — and
harder to catch, because "we've seen this before" is exactly the kind of claim
people stop questioning.

**Tenant isolation is structural, from the first commit.** Retrofitting it is how
leaks happen, so a query cannot be made without a tenant and there is no method
that reads across tenants.

**Written knowledge arrives untrusted.** A runbook is a document, and documents
can be edited by anyone who can reach the repository. Ingested text is stored
`UNTRUSTED` and must be explicitly promoted before it can inform a decision.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

EMBEDDING_DIMENSIONS = 512
DEFAULT_RETENTION = timedelta(days=90)

MIN_SIMILARITY = 0.35
"""Below this, a text match is noise rather than a resemblance.

A threshold rather than always returning the top-k: top-k with no floor always
returns something, which is how a system ends up asserting a precedent for an
incident it has never seen anything like."""


class MemoryKind(StrEnum):
    INCIDENT = "incident"
    RUNBOOK = "runbook"
    DECISION = "decision"
    """An architecture decision — why the system is shaped the way it is. Often
    the actual answer to "why does this keep happening?"."""


class Trust(StrEnum):
    UNTRUSTED = "untrusted"
    """Ingested but not validated. Retrievable for context, never cited as
    authority, and never promoted automatically."""

    VERIFIED = "verified"
    """Promoted by a named actor who vouched for it."""


class MatchBasis(StrEnum):
    """*Why* a memory matched. The distinction is the point of hybrid retrieval.

    Ordered strongest to weakest, and worded so the difference survives into the
    UI: "this happened on this service before" and "this reads like something
    that happened elsewhere" are different claims, and collapsing them into one
    relevance score throws away the part an operator needs.
    """

    SAME_ENTITY = "same_entity"
    """The same entity failed before. The strongest form of precedent."""

    SAME_SIGNAL = "same_signal"
    """The same failure mode, elsewhere. Useful, and a different claim."""

    TEXT_ONLY = "text_only"
    """Reads similar, shares no structure. Weakest — surfaced, but labelled, and
    never presented as "we have seen this before"."""


@dataclass(frozen=True)
class Outcome:
    """What actually happened to a past incident.

    Every field is optional except `resolved`, because an honest record of a
    half-finished investigation is more useful than a tidy fabricated one.
    """

    resolved: bool
    diagnosis_correct: bool | None = None
    """`False` is the most valuable value here, and the one a naive
    implementation drops. It is why `warning` exists."""

    action_taken: str | None = None
    verification_passed: bool | None = None
    note: str | None = None

    @property
    def warning(self) -> str | None:
        """What must be said out loud when this memory is recalled.

        Surfacing a prior incident whose diagnosis was wrong, without saying so,
        lends the authority of history to a mistake.
        """
        if self.diagnosis_correct is False:
            return "the diagnosis on this prior incident was later found to be wrong"
        if self.verification_passed is False:
            return "the remediation on this prior incident failed verification"
        if not self.resolved:
            return "this prior incident was never resolved"
        return None


@dataclass
class MemoryRecord:
    """One thing remembered, with everything needed to judge it.

    Provenance is mandatory in spirit and in practice: `source`, `at` and `owner`
    are how a human decides whether a recollection is worth acting on, and a
    memory without them is an assertion from nowhere.
    """

    id: str
    tenant: str
    kind: MemoryKind
    text: str
    source: str
    at: datetime
    owner: str | None = None
    confidence: float = 1.0
    trust: Trust = Trust.UNTRUSTED
    retention: timedelta = DEFAULT_RETENTION
    entities: frozenset[str] = frozenset()
    signals: frozenset[str] = frozenset()
    outcome: Outcome | None = None
    embedding: tuple[float, ...] = ()

    def expired(self, now: datetime) -> bool:
        return now - self.at > self.retention


@dataclass(frozen=True)
class Recollection:
    """A retrieved memory, with why it matched and how strongly."""

    record: MemoryRecord
    basis: MatchBasis
    similarity: float
    score: float

    @property
    def is_precedent(self) -> bool:
        """Whether this supports the phrase "we have seen this before".

        A text-only resemblance does not. Saying it does is how a coincidence of
        vocabulary becomes a claim about history.
        """
        return self.basis in (MatchBasis.SAME_ENTITY, MatchBasis.SAME_SIGNAL)

    def describe(self) -> str:
        match self.basis:
            case MatchBasis.SAME_ENTITY:
                head = "The same entity had a similar incident before"
            case MatchBasis.SAME_SIGNAL:
                head = "The same failure mode was seen elsewhere before"
            case _:
                head = "A past record reads similarly (no shared entity or signal)"

        parts = [f"{head}: {self.record.id}"]
        if self.record.outcome is not None:
            if warning := self.record.outcome.warning:
                parts.append(f"CAUTION — {warning}")
            elif self.record.outcome.action_taken:
                parts.append(f"resolved by: {self.record.outcome.action_taken}")
        return ". ".join(parts)


# --- embedding ----------------------------------------------------------------


class Embedder(Protocol):
    """Whatever turns text into a vector.

    A protocol for the same reason `Provider` is one: core must run on a laptop
    with no credentials, and the retrieval logic must not know or care whether
    the vectors came from a hosted model or from the local fallback below.
    """

    dimensions: int

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...


_TOKEN = re.compile(r"[a-z0-9_]+")


class HashingEmbedder:
    """A local, dependency-free embedder using the hashing trick.

    Not a stub — a hashing vectorizer over token bigrams is a real technique, and
    it captures lexical overlap well enough to be useful. It does not capture
    meaning: "pool exhausted" and "no free connections" describe the same failure
    and will not match here.

    That limitation is deliberate and is the point of the hybrid design. Because
    the default embedder is lexical, the structured filters are doing most of the
    work — so retrieval degrades honestly rather than silently when no hosted
    embedder is configured, and swapping one in improves recall without changing
    any calling code.
    """

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> tuple[float, ...]:
        tokens = _TOKEN.findall(text.lower())
        # Bigrams alongside unigrams, so word order carries a little weight —
        # "pool exhausted" and "exhausted pool" are not identical.
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]

        vector = [0.0] * self.dimensions
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            # Signed, so unrelated features cancel instead of accumulating.
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return tuple(vector)
        return tuple(value / norm for value in vector)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b))))


# --- the store ----------------------------------------------------------------


class Smriti:
    """Tenant-isolated memory with hybrid retrieval.

    In-memory here. The interface is what matters: the same shape backs a vector
    database later, and no caller learns which — the Graph ADR's lesson, that the
    storage decision should be a measurement rather than an assumption.
    """

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or HashingEmbedder()
        self._by_tenant: dict[str, dict[str, MemoryRecord]] = {}

    # -- writing ----------------------------------------------------------

    def remember(self, record: MemoryRecord) -> MemoryRecord:
        """Store one memory, embedding it on the way in.

        Returns the stored record so a caller can see what was actually kept —
        including the trust level, which is not necessarily what was asked for.
        """
        if not record.tenant:
            raise ValueError("a memory without a tenant cannot be stored safely")
        if not record.embedding:
            record.embedding = self.embedder.embed([record.text])[0]
        self._by_tenant.setdefault(record.tenant, {})[record.id] = record
        return record

    def ingest_document(
        self,
        tenant: str,
        doc_id: str,
        text: str,
        kind: MemoryKind,
        source: str,
        at: datetime,
        entities: Iterable[str] = (),
        signals: Iterable[str] = (),
    ) -> MemoryRecord:
        """Ingest a runbook or decision record — always as `UNTRUSTED`.

        There is deliberately no `trust=` parameter. A runbook is a document that
        anyone with repository access can edit, and a parameter here is a
        parameter someone passes `VERIFIED` to while wiring up an importer. The
        only way to trusted is `promote`, which requires a named human.
        """
        return self.remember(
            MemoryRecord(
                id=doc_id,
                tenant=tenant,
                kind=kind,
                text=text,
                source=source,
                at=at,
                trust=Trust.UNTRUSTED,
                entities=frozenset(entities),
                signals=frozenset(signals),
            )
        )

    def promote(self, tenant: str, memory_id: str, by: str, note: str | None = None) -> MemoryRecord:
        """Mark a memory trusted. Requires an actor, who is recorded as owner.

        The validation step the security model asks for: untrusted external
        content must never become trusted permanent memory on its own.
        """
        if not by:
            raise ValueError("promotion requires a named actor — trust needs an owner")
        record = self._require(tenant, memory_id)
        record.trust = Trust.VERIFIED
        record.owner = by
        if note:
            record.text = f"{record.text}\n\n[verified by {by}: {note}]"
            record.embedding = self.embedder.embed([record.text])[0]
        return record

    def record_outcome(self, tenant: str, memory_id: str, outcome: Outcome) -> MemoryRecord:
        """Attach what actually happened.

        Separate from `remember` because the outcome is usually known much later,
        and because a memory stored without one should be visibly incomplete
        rather than defaulted to "resolved".
        """
        record = self._require(tenant, memory_id)
        record.outcome = outcome
        return record

    # -- reading ----------------------------------------------------------

    def recall(
        self,
        tenant: str,
        text: str,
        entities: Iterable[str] = (),
        signals: Iterable[str] = (),
        limit: int = 5,
        now: datetime | None = None,
        min_similarity: float = MIN_SIMILARITY,
        exclude: str | None = None,
    ) -> list[Recollection]:
        """Find prior memories resembling this situation.

        `tenant` is positional and required — there is no overload that omits it,
        and no method anywhere that reads across tenants.

        Returns an empty list when nothing matches, which is the honest answer.
        Nothing here manufactures a precedent to avoid returning nothing.
        """
        now = now or datetime.now().astimezone()
        entity_set, signal_set = frozenset(entities), frozenset(signals)
        query = self.embedder.embed([text])[0]

        results: list[Recollection] = []
        for record in self._by_tenant.get(tenant, {}).values():
            if record.id == exclude or record.expired(now):
                continue

            similarity = cosine(query, record.embedding)
            basis = self._basis(record, entity_set, signal_set)

            # A text-only match must clear the similarity floor on its own. A
            # structural match may be surfaced on weaker text similarity, because
            # the structure is itself evidence of relatedness — that asymmetry is
            # the hybrid part, and it is why this is not a single blended score.
            if basis is MatchBasis.TEXT_ONLY and similarity < min_similarity:
                continue

            results.append(
                Recollection(
                    record=record,
                    basis=basis,
                    similarity=round(similarity, 4),
                    score=round(self._score(basis, similarity, record), 4),
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def precedents(self, tenant: str, text: str, **kwargs: object) -> list[Recollection]:
        """Only matches that justify the phrase "we have seen this before"."""
        return [r for r in self.recall(tenant, text, **kwargs) if r.is_precedent]  # type: ignore[arg-type]

    # -- internals --------------------------------------------------------

    @staticmethod
    def _basis(
        record: MemoryRecord, entities: frozenset[str], signals: frozenset[str]
    ) -> MatchBasis:
        if entities & record.entities:
            return MatchBasis.SAME_ENTITY
        if signals & record.signals:
            return MatchBasis.SAME_SIGNAL
        return MatchBasis.TEXT_ONLY

    @staticmethod
    def _score(basis: MatchBasis, similarity: float, record: MemoryRecord) -> float:
        """Rank within a basis, never across it.

        The basis weights are separated far enough that a strong text-only match
        cannot outrank a weak same-entity one. That is deliberate: the whole point
        of hybrid retrieval is that shared structure means more than shared
        vocabulary, and a single blended score would let a coincidence of phrasing
        win on a good enough embedding.
        """
        weight = {
            MatchBasis.SAME_ENTITY: 2.0,
            MatchBasis.SAME_SIGNAL: 1.0,
            MatchBasis.TEXT_ONLY: 0.0,
        }[basis]
        # Verified memories edge out unverified ones at equal relevance, but the
        # bonus is small — trust is not relevance, and a verified runbook about
        # something else is still about something else.
        trust_bonus = 0.05 if record.trust is Trust.VERIFIED else 0.0
        return weight + similarity + trust_bonus

    def _require(self, tenant: str, memory_id: str) -> MemoryRecord:
        try:
            return self._by_tenant[tenant][memory_id]
        except KeyError:
            raise KeyError(f"no memory {memory_id!r} for tenant {tenant!r}") from None

    def __len__(self) -> int:
        return sum(len(records) for records in self._by_tenant.values())

    def count(self, tenant: str) -> int:
        return len(self._by_tenant.get(tenant, {}))


# --- measurement --------------------------------------------------------------


@dataclass
class RetrievalQuality:
    """How well recall found what it should have.

    Retrieval quality is measured rather than assumed because the ADR's choice —
    hybrid over pure vector — is a claim that has to be checkable, and because a
    hosted embedder should be adoptable on evidence rather than on the assumption
    that a bigger model retrieves better.
    """

    hits: int = 0
    misses: int = 0
    false_precedents: int = 0
    """Surfaced as "we have seen this before" when the truth was unrelated.

    Reported separately, and it is the number to watch: a missed precedent costs
    an operator the time they would have spent anyway, while a false one sends
    them confidently down a path that does not exist.
    """

    @property
    def recall_at_k(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    def summary(self) -> dict[str, object]:
        return {
            "recall_at_k": self.recall_at_k,
            "hits": self.hits,
            "misses": self.misses,
            "false_precedents": self.false_precedents,
        }


def score_retrieval(cases: list[tuple[list[Recollection], str | None]]) -> RetrievalQuality:
    """Score recall against known-correct prior incidents.

    Each case pairs the recollections returned with the id of the memory that
    *should* have been found, or `None` when the correct answer is to find
    nothing — the negative case, without which a retriever that returns
    everything scores perfectly.
    """
    quality = RetrievalQuality()
    for recollections, expected in cases:
        ids = [r.record.id for r in recollections]
        precedent_ids = [r.record.id for r in recollections if r.is_precedent]

        if expected is None:
            if precedent_ids:
                quality.false_precedents += 1
            else:
                quality.hits += 1
            continue

        if expected in ids:
            quality.hits += 1
        else:
            quality.misses += 1
        if any(pid != expected for pid in precedent_ids):
            quality.false_precedents += 1
    return quality
