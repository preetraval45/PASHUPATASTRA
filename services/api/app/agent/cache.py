"""Answers, kept so the same question is not paid for twice.

On a public console most questions are the same question. The starter chips are
fixed text, the incidents do not change, and a visitor who clicks "what
happened?" is asking exactly what the last visitor asked. Without a cache each
one costs a full turn against an 8,000-token-per-minute allowance, and the
second visitor in a minute waits for a rate limit to clear for an answer already
computed.

The key covers everything that could change the answer — the incident, the
question, the model, the instructions, and the evidence itself. Leave any of
them out and the cache serves a stale answer after a change, which is worse than
no cache: it is a wrong answer with no way to notice.

Durable when a durable store exists, which is what makes it worth having. A
per-process cache on Lambda warms up and is then thrown away with the container.
"""

from __future__ import annotations

import hashlib

VERSION = "1"
"""Bumped when the instructions or the answer shape change. Answers computed
under different instructions are not interchangeable, and the version is what
retires them without anyone having to remember to clear anything."""


def key(
    incident_id: str,
    question: str,
    model: str,
    instructions: str,
    evidence_refs: list[str],
) -> str:
    """A digest of everything that determines the answer.

    The question is normalised for case and surrounding space, so "What
    happened?" and "what happened? " share an entry. Nothing further — collapsing
    punctuation or stemming would merge questions that differ in meaning, and a
    cache that answers a question nobody asked is indistinguishable from a model
    that hallucinated.
    """
    digest = hashlib.sha256()
    for part in (
        VERSION,
        incident_id,
        " ".join(question.lower().split()),
        model,
        hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
        ",".join(sorted(evidence_refs)),
    ):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:32]


class AnswerCache:
    """Durable when a durable backend exists, in-process when it does not.

    The backend is resolved on each access through `backend.durable()` — the one
    resolver R18 established — rather than being handed in by a caller. Passing
    it in meant the cache was bound on the first question a container answered
    and not before, so `/health` could only ever report it unbound, and there
    was no way to tell a cache that was working from one that was not.

    Resolution is cheap: `durable()` decides once per process and returns the
    same object afterwards.
    """

    def __init__(self, resolver=None) -> None:
        self._resolver = resolver
        self._local: dict[str, dict] = {}

    @property
    def store(self):
        if self._resolver is not None:
            return self._resolver()
        from ..backend import durable

        return durable()

    @property
    def durable(self) -> bool:
        return hasattr(self.store, "get_cached_answer")

    def get(self, digest: str) -> dict | None:
        store = self.store
        if hasattr(store, "get_cached_answer"):
            found = store.get_cached_answer(digest)
            if found is not None:
                return found
        return self._local.get(digest)

    def put(self, digest: str, answer: dict) -> None:
        self._local[digest] = answer
        store = self.store
        if hasattr(store, "put_cached_answer"):
            store.put_cached_answer(digest, answer)


CACHE = AnswerCache()
"""Process-wide, like the audit log and the store.

Built per call it was useless: the in-process half started empty every time, so
nothing was ever served from it, and the durable half did all the work alone.
A cache with request lifetime is not a cache.
"""


def shared(_store=None) -> AnswerCache:
    """The process cache. The argument is ignored and kept only so callers do
    not have to change; the cache resolves its own backend now."""
    return CACHE
