"""What the console already knows about one indicator (R78).

The lookup behind every clickable address, hash and domain in the interface.
It reads the store and **nothing else**, which is the decision worth stating
rather than the limitation it looks like.

R24 settled it for the feeds and the same argument settles it here: asking a
third party about an address tells that third party which address we are
looking at. Doing that per observation, from a page, would publish the
reader's attention to abuse.ch — every indicator they hovered, in order. The
feeds already fetch these catalogues wholesale on a schedule; a lookup against
what they stored answers the same question and tells nobody. So there is no
"before it queries anything external" path here, because there is no external
query, and the response says so in a field instead of leaving a reader to
assume one happened.

A miss is an answer. `known: false` with the sources that were consulted is
what "nothing known" looks like, and it is a 200 — a 404 would say the request
was wrong when the request was fine and the catalogues simply have nothing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from pashupatastra.indicators import IndicatorKind, candidate_keys, classify

TTL_SECONDS = 600.0
"""How long a looked-up answer stays good. The feeds poll hourly, so ten
minutes is well inside the window in which the answer cannot have changed —
and the point of the cache is the page that renders forty indicators and the
reader who clicks six of them, not the hour."""

MAX_REPORTS = 25
"""Reports returned for one indicator. The grouping window (R56) already found
one address reported forty-three times; a popover is not where all of them
belong, and the count says how many there were."""


@dataclass
class _Entry:
    value: dict
    at: float


@dataclass
class Enricher:
    """Lookups against the store, with a short in-process cache.

    In-process, so a cold container starts cold — which is correct here: the
    alternative is a cache in the table, and a durable cache of an answer the
    hourly poll can change is one more thing that can be stale in a way nobody
    notices. A cold start pays two gets.
    """

    store: Any
    cache: dict[str, _Entry] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    def lookup(self, raw: str, now: float | None = None) -> dict | None:
        """What is held about `raw`, or `None` if it is not an indicator at all.

        `None` is not "nothing known" — it is "that is not a thing this route
        will look up", and the caller turns it into a refusal. The distinction
        is the guard: `account:j.rivera` must not be answerable here, and an
        empty result would be an answer about an account.
        """
        value = (raw or "").strip()
        kind = classify(value)
        if kind is None:
            return None

        now = now if now is not None else time.monotonic()
        key = f"{kind.value}:{value.lower()}"
        cached = self.cache.get(key)
        if cached is not None and now - cached.at < TTL_SECONDS:
            self.hits += 1
            return {**cached.value, "cached": True}

        self.misses += 1
        answer = self._read(value, kind)
        self.cache[key] = _Entry(value=answer, at=now)
        return {**answer, "cached": False}

    def _read(self, value: str, kind: IndicatorKind) -> dict:
        keys = candidate_keys(value, kind)
        reader = getattr(self.store, "entity_events", None)
        rows: list[dict] = []
        if reader is not None:
            for key in keys:
                rows.extend(reader(key, limit=MAX_REPORTS) or [])

        rows.sort(key=lambda row: str(row.get("occurred_at", "")), reverse=True)
        seen: set[str] = set()
        reports: list[dict] = []
        for row in rows:
            identifier = str(row.get("id") or "")
            if identifier in seen:
                continue
            seen.add(identifier)
            labels = row.get("labels") or {}
            provenance = row.get("provenance") or {}
            reports.append(
                {
                    "event_id": identifier,
                    "source": row.get("source"),
                    "occurred_at": row.get("occurred_at"),
                    "severity": row.get("severity"),
                    "verification": labels.get("verification"),
                    "title": labels.get("title") or labels.get("summary") or "",
                    # The advisory *about* the thing, never the thing: a
                    # URLhaus entry's own url is a live malware distribution
                    # point, and R24 settled that it is never rendered.
                    "url": provenance.get("url"),
                }
            )
            if len(reports) >= MAX_REPORTS:
                break

        stamps = [r["occurred_at"] for r in reports if r["occurred_at"]]
        return {
            "value": value,
            "kind": kind.value,
            "known": bool(reports),
            "reports": reports,
            "report_count": len(reports),
            "sources": sorted({str(r["source"]) for r in reports if r["source"]}),
            "first_seen": min(stamps) if stamps else None,
            "last_seen": max(stamps) if stamps else None,
            "keys_tried": keys,
            # Said in the answer rather than assumed by the reader. "Nothing
            # known" means nothing known *here*, and a reader deciding what to
            # do with that needs to know what was asked.
            "consulted": "this console's own store, populated by the scheduled feed poll",
            "queried_externally": False,
            "note": (
                "No third party was asked. Querying a catalogue per indicator "
                "would tell that catalogue which indicators are being read."
            ),
        }


__all__ = ["MAX_REPORTS", "TTL_SECONDS", "Enricher"]
