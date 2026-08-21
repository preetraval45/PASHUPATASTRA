"""Polling the feeds, once per schedule, without re-importing what is already in.

A cursor per feed holds the newest entry timestamp successfully stored. The next
run asks only for entries after it. Without that, an hourly poll of a catalogue
that changes daily would rewrite the same 25 rows 24 times a day and present
five-year-old advisories as new every time.

The cursor is advanced **after** the write, not before. Advancing first means a
failed write silently skips those entries forever, and the gap is invisible —
the feed looks quiet rather than broken.
"""

from __future__ import annotations

import logging

from .sources import FEEDS, FeedUnavailable

log = logging.getLogger(__name__)

DEFAULT_LIMIT = 25
"""Per feed, per run. The catalogues hold thousands; what is wanted is what
changed. This is also the write-rate ceiling on a 25-unit DynamoDB table —
two feeds at 25 entries an hour is nothing, and an unbounded first run of
16,000 URLhaus rows would not be."""

FIRST_RUN_LIMIT = 12
"""Smaller. On the first run every entry is 'new', and the point of the first
run is to have something to show, not to import a catalogue."""


def run(store, cursors, limit: int = DEFAULT_LIMIT) -> dict[str, object]:
    """Poll every feed and store what is new. Returns what happened, per feed.

    One feed failing does not stop the others. Intelligence sources are third
    parties with their own outages, and a run that aborts because abuse.ch was
    briefly down would also skip CISA — turning someone else's five minutes of
    downtime into a gap in ours.
    """
    summary: dict[str, object] = {}

    for name, fetch in FEEDS.items():
        since = cursors.get_feed_cursor(name)
        try:
            events = fetch(limit=limit if since else FIRST_RUN_LIMIT, since=since)
        except FeedUnavailable as error:
            # Recorded, not raised. The next run tries again, and a reader can
            # see which feed is stale rather than wondering why it is quiet.
            log.warning("feed %s unavailable: %s", name, error)
            summary[name] = {"ok": False, "error": str(error)[:200], "stored": 0}
            continue

        if not events:
            summary[name] = {"ok": True, "stored": 0, "cursor": since}
            continue

        store.save_events(events)

        # The newest offset actually written, taken from provenance rather than
        # from the fetch parameters — what was asked for and what was stored are
        # different facts, and the cursor must follow the second.
        newest = max(
            (event.provenance.offset for event in events if event.provenance.offset),
            default=since,
        )
        if newest:
            cursors.set_feed_cursor(name, newest)

        summary[name] = {"ok": True, "stored": len(events), "cursor": newest}
        log.info("feed %s stored %d entries up to %s", name, len(events), newest)

    return summary


class MemoryCursors:
    """Cursors for a deployment with no durable store.

    Every run then looks like a first run, which is correct rather than
    convenient: nothing was durably stored either, so nothing should be skipped.
    """

    def __init__(self) -> None:
        self._at: dict[str, str] = {}

    def get_feed_cursor(self, feed: str) -> str | None:
        return self._at.get(feed)

    def set_feed_cursor(self, feed: str, value: str) -> None:
        self._at[feed] = value


def cursors_for(backend) -> object:
    """The durable cursor store when there is one, memory otherwise."""
    if backend is not None and hasattr(backend, "get_feed_cursor"):
        return backend
    return MemoryCursors()
