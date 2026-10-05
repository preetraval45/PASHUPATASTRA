"""What this project has actually done, counted from the things that did it (R107).

Every figure here names where it came from, and every one of them is a recount
of a source that exists for another reason — the feed store, the audit ledger,
the warm task's heartbeat, git. Nothing is incremented by a dashboard and kept
on its own; `scripts/verifyimpact.py` reads the same sources and compares.

That constraint is the whole point rather than tidiness. A page of numbers
about a project is exactly where a number nobody can recompute would go
unnoticed, and this one is meant to be read by people whose job is to doubt it.
So each figure carries a `from` saying what was counted, and a figure whose
source is unreachable is reported **absent** rather than as zero — a zero is a
measurement and absence is not.

**Page views are renders, not people.** Counted on the server that rendered the
page, with no cookie and no beacon in the browser. Unique visitors would need
an identifier per person, and R28 settled that this site does not mint one —
the Blue Team token is an opaque per-browser id precisely so that it cannot
become one. Nothing authenticates the count either, and the page says so:
somebody determined could inflate it, and a number that can be inflated should
say that out loud rather than be presented as audited.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .engines.audit import AuditKind
from .tasks import EXPECTED_BEATS_PER_DAY

MILESTONES = Path(__file__).resolve().parents[3] / "docs" / "milestones.json"

GITHUB_REPO = "preetraval45/PASHUPATASTRA"
GITHUB_TTL = timedelta(hours=1)
"""Cached for an hour. GitHub allows sixty unauthenticated requests an hour per
address and this is read on a page anyone can open; a lookup per view would
spend the allowance and then start reporting the figures as absent."""

_github: dict[str, Any] = {"at": None, "value": None}


def absent(why: str) -> dict[str, Any]:
    """A figure that could not be measured. Not zero — zero is a measurement."""
    return {"value": None, "absent": why}


def measured(value: Any, source: str) -> dict[str, Any]:
    return {"value": value, "from": source}


def github(now: datetime | None = None, fetch: Any = None) -> dict[str, Any]:
    """Stars, forks and contributors, cached. Absent rather than zero when
    GitHub cannot be reached — nobody starring a repository and GitHub being
    unreachable are different facts."""
    now = now or datetime.now(UTC)
    if _github["at"] is not None and now - _github["at"] < GITHUB_TTL:
        return _github["value"]

    fetch = fetch or _fetch_github
    try:
        value = fetch()
    except Exception as error:  # noqa: BLE001 — any failure is "we could not ask"
        return absent(f"GitHub did not answer: {type(error).__name__}")
    _github["at"], _github["value"] = now, value
    return value


def _fetch_github() -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}",
        headers={"User-Agent": "pashupatastra", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        body = json.load(response)
    return measured(
        {
            "stars": body.get("stargazers_count", 0),
            "forks": body.get("forks_count", 0),
            "watchers": body.get("subscribers_count", 0),
            "open_issues": body.get("open_issues_count", 0),
        },
        f"api.github.com/repos/{GITHUB_REPO}",
    )


def milestones() -> dict[str, Any]:
    """The timeline, generated from git by `scripts/milestones.py`.

    Committed rather than read from git at request time: the Lambda has no
    repository. Generated rather than written, so the page cannot list a
    milestone that never landed — the generator reads commit subjects for
    `(R##)` and takes the date from the commit.
    """
    if not MILESTONES.exists():
        return absent("docs/milestones.json has not been generated")
    try:
        data = json.loads(MILESTONES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return absent(f"docs/milestones.json unreadable: {type(error).__name__}")
    return measured(data.get("milestones", []), "git commit subjects carrying (R##)")


def uptime(store: Any, days: int = 30) -> dict[str, Any]:
    """The share of the warm task's expected beats that actually happened.

    R99 writes one beat every five minutes. A day with every beat is a day the
    function answered all day; fewer is time it did not. Absent where the store
    keeps no heartbeat, which is every store but the deployed one.
    """
    reader = getattr(store, "heartbeats", None)
    if reader is None:
        return absent("this store keeps no heartbeat")
    beats = reader(days)
    if not beats:
        return absent("no heartbeat recorded yet — the warm schedule may not be running")
    counted = sum(beats.values())
    expected = EXPECTED_BEATS_PER_DAY * len(beats)
    return measured(
        {
            "days": len(beats),
            "beats": counted,
            "expected": expected,
            "share": round(counted / expected, 4) if expected else None,
            "by_day": beats,
        },
        f"the warm task's heartbeat, {EXPECTED_BEATS_PER_DAY} expected a day (R99)",
    )


def views(store: Any, days: int = 30) -> dict[str, Any]:
    reader = getattr(store, "views", None)
    if reader is None:
        return absent("this store counts no views")
    by_day = reader(days)
    if not by_day:
        return absent("no page has been rendered since this store was created")
    total = sum(sum(routes.values()) for routes in by_day.values())
    by_route: dict[str, int] = {}
    for routes in by_day.values():
        for route, count in routes.items():
            by_route[route] = by_route.get(route, 0) + count
    return measured(
        {
            "total": total,
            "days": len(by_day),
            "by_day": {day: sum(routes.values()) for day, routes in by_day.items()},
            "by_route": dict(sorted(by_route.items(), key=lambda kv: -kv[1])),
        },
        "counted on the server that rendered each page — renders, not people",
    )


def ledger(audit, since_days: int = 3650) -> dict[str, Any]:
    """Agent turns, Blue Team attempts and the size of the trail, from the
    ledger itself rather than from counters kept beside it."""
    reader = getattr(audit, "since", None)
    if reader is None:
        return absent("this audit log cannot be read by window")
    rows = reader(datetime.now(UTC) - timedelta(days=since_days))
    kinds: dict[str, int] = {}
    for record in rows:
        kinds[record.kind.value] = kinds.get(record.kind.value, 0) + 1
    return measured(
        {
            "records": len(rows),
            "agent_turns": kinds.get(AuditKind.AGENT_TURN.value, 0),
            "by_kind": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
        },
        "the append-only audit ledger",
    )


def intelligence(store: Any, feeds: dict[str, Any]) -> dict[str, Any]:
    """Indicators and reports ingested, and where each feed has reached."""
    reader = getattr(store, "recent_events", None)
    if reader is None:
        return absent("this store cannot report what it has ingested")
    rows = reader(sources=sorted(feeds), limit=5000)
    by_source: dict[str, int] = {}
    indicators: set[str] = set()
    for row in rows:
        by_source[str(row.get("source"))] = by_source.get(str(row.get("source")), 0) + 1
        if row.get("entity_key"):
            indicators.add(str(row["entity_key"]))
    return measured(
        {
            "reports": len(rows),
            "indicators": len(indicators),
            "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
            "feeds": len(feeds),
        },
        "events stored by the scheduled feed poll",
    )


__all__ = [
    "GITHUB_REPO",
    "absent",
    "github",
    "intelligence",
    "ledger",
    "measured",
    "milestones",
    "uptime",
    "views",
]
