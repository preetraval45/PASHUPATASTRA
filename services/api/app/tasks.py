"""Scheduled work the Lambda handler dispatches — nothing HTTP.

Kept apart from `handler.py` because that module imports `mangum`, which is a
Lambda-only dependency, and these functions are worth testing everywhere.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

SCHEDULED_TASK = "ingest_feeds"
WARM_TASK = "warm"

EXPECTED_BEATS_PER_DAY = 288
"""One warm invocation every five minutes. `/impact` reads uptime as the share
of these that happened (R107)."""


def ingest() -> dict[str, object]:
    """Poll the threat feeds. Imported inside the function so an HTTP request
    never pays for modules it will not use."""
    from .backend import durable
    from .feeds.ingest import cursors_for, run
    from .graph import entitystore

    backend = durable()
    summary = run(store=entitystore(), cursors=cursors_for(backend), limit=25)
    logging.getLogger(__name__).info("feed ingest: %s", summary)
    return {"task": SCHEDULED_TASK, "feeds": summary, "durable": backend is not None}


def warm() -> dict[str, object]:
    """Keep one container alive and its indexes primed, and leave a heartbeat.

    Every five minutes from EventBridge (R99) — 8,640 invocations a month
    against an always-free million. A visitor then almost never pays the cold
    start, and the recent-events index is read here first so the first real
    request finds it built. The heartbeat is one counter per UTC day, which
    `/impact` later reads as uptime (R107): a day with 288 beats was a day the
    function answered every five minutes.
    """
    from .backend import durable
    from .graph import entitystore

    store = entitystore()
    reader = getattr(store, "recent_events", None)
    primed = len(reader(limit=1)) if reader else 0
    backend = durable()
    beat = getattr(backend, "heartbeat", None)
    beats = beat(datetime.now(UTC).date().isoformat()) if beat else None
    return {
        "task": WARM_TASK,
        "primed": primed,
        "beats_today": beats,
        "durable": backend is not None,
    }
