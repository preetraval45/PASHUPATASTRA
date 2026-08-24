"""One row per indicator, not one per report.

abuse.ch publishes a submission every time somebody sees a URL, so a single
address reported forty-three times in an afternoon arrived as forty-three
near-identical cards. That is not intelligence, it is the same fact repeated
until the page reads as output from a script — and it buried the other hundred
and seven indicators underneath it.

Grouped here rather than in the browser, for the same reason the incident
sub-graph is filtered here: the page should not receive two hundred rows to
render a hundred and eight, and the collapsing has to be testable against a
fixture with a known duplicate count.

**Nothing is discarded.** Every individual report — its timestamp, reporter,
tags and status — stays in the group it belongs to. The complaint was that
repetition drowned the signal, not that the repetitions were worthless: eight
independent sightings is itself a fact about an indicator, and it is now a fact
the page can state instead of a scroll the reader has to perform.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

GROUPING_WINDOW = timedelta(hours=3)
"""How recent a report must be, relative to the newest one for that indicator,
to count towards the headline.

A named constant because it appears in three places — the count, the phrase the
page prints, and the test — and a literal `3` scattered across those is three
things to change and two chances to forget one.

Three hours is a starting point rather than a finding. It is long enough that a
campaign reported through an afternoon reads as one indicator, and short enough
that the same address seen again next week reads as new activity.
"""


def _parsed(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _report(entry: dict) -> dict[str, Any]:
    """One sighting, reduced to what distinguishes it from the others."""
    labels = entry.get("labels") or {}
    return {
        "id": entry.get("id"),
        "at": entry.get("occurred_at"),
        "status": labels.get("status") or None,
        "tags": labels.get("tags") or None,
        "summary": labels.get("summary") or "",
        "url": (entry.get("provenance") or {}).get("url"),
    }


def group(entries: Iterable[dict], window: timedelta = GROUPING_WINDOW) -> list[dict]:
    """Collapse repeated reports of the same indicator into one row each.

    The window is rolling *relative to each indicator's own latest report*, not
    to the wall clock. An indicator last seen yesterday should still say how
    many times it was reported in the three hours around that activity —
    anchoring to now would report every one of them as zero and make the count
    a function of when the page happened to load.
    """
    buckets: dict[str, list[dict]] = {}
    for entry in entries:
        key = entry.get("entity_key")
        if key:
            buckets.setdefault(key, []).append(entry)

    grouped: list[dict] = []
    for key, rows in buckets.items():
        rows.sort(key=lambda row: str(row.get("occurred_at", "")), reverse=True)
        newest, oldest = rows[0], rows[-1]
        labels = newest.get("labels") or {}

        latest_at = _parsed(newest.get("occurred_at"))
        within = rows
        if latest_at is not None:
            within = [
                row
                for row in rows
                if (at := _parsed(row.get("occurred_at"))) is not None
                and latest_at - at <= window
            ] or rows

        grouped.append(
            {
                "entity_key": key,
                "source": newest.get("source"),
                "severity": newest.get("severity"),
                "verification": labels.get("verification"),
                "title": labels.get("title") or key,
                "summary": labels.get("summary") or "",
                "provenance": newest.get("provenance") or {},
                "labels": labels,
                "reports": len(rows),
                "reports_in_window": len(within),
                "window_hours": int(window.total_seconds() // 3600),
                "first_at": oldest.get("occurred_at"),
                "last_at": newest.get("occurred_at"),
                # The *latest* report's status, not "any report said online".
                # An indicator whose most recent sighting says offline has gone
                # offline; carrying the optimistic reading forward would leave
                # dead infrastructure on the board as a live threat.
                "active": labels.get("status") == "online",
                "history": [_report(row) for row in rows],
            }
        )

    # Most recent activity first. The count is not the ordering: forty-three
    # sightings of something last seen on Tuesday matters less than one sighting
    # from ten minutes ago.
    grouped.sort(key=lambda row: str(row.get("last_at", "")), reverse=True)
    return grouped
