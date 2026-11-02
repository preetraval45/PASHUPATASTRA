"""Past incidents: every exploited CVE CISA has catalogued, every breach HIBP has published, and
a year of critical CVEs from NVD.

`scripts/fetchhistory.py` writes the records at deploy time, in the shape the feed poll stores;
this builds incidents from them with the same rules as the live ones (`liveincidents.py`), without
the live windows, under the `PAST-` prefix. They are what an analyst means by "has this happened
before": thousands of real incidents, each citing its record, which `/events/{id}` resolves here.

Read once per process. A deployment without the file (a local run, or a deploy whose fetch
failed) has no history, and says so through `available()`, rather than inventing any.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from pashupatastra import Incident

from . import liveincidents as rules

PREFIX = "PAST-"
FILE = Path(__file__).resolve().parents[1] / "history" / "history.json"


def is_past(incident_id: str) -> bool:
    return incident_id.startswith(PREFIX)


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"generated": None, "records": []}


def available() -> dict[str, object]:
    data = _data()
    return {"generated": data.get("generated"), "records": len(data.get("records") or [])}


@lru_cache(maxsize=1)
def _by_id() -> dict[str, dict]:
    return {r["id"]: r for r in _data().get("records") or []}


def event(event_id: str) -> dict | None:
    """One history record, in the shape `/events/{id}` returns for a stored event."""
    record = _by_id().get(event_id)
    if record is None:
        return None
    return {"event_class": "security", "observed_at": _data().get("generated"), "severity": None,
            "payload": {}, **record}


@lru_cache(maxsize=1)
def incidents() -> tuple[Incident, ...]:
    records = _data().get("records") or []
    now = datetime.now(UTC)

    def older(source: str, days: int) -> list[dict]:
        # The past begins where the live window ends, so no incident is listed twice.
        return [r for r in records if r["source"] == source
                and (rules._when(r) or now) < now - timedelta(days=days)]

    exploited = {r["entity_key"] for r in records if r["source"] == "cisa-kev"}
    built = (
        rules._kev(older("cisa-kev", rules.KEV_DAYS), now, days=None, prefix=PREFIX)
        + rules._breaches(older("hibp", rules.BREACH_DAYS), now, days=None, prefix=PREFIX)
        # A disclosure CISA later confirmed exploited is listed once, as exploited.
        + rules._nvd([r for r in older("nvd", rules.NVD_DAYS) if r["entity_key"] not in exploited],
                     now, days=None, prefix=PREFIX)
    )
    built.sort(key=lambda i: i.opened_at, reverse=True)
    return tuple(built)


def get(incident_id: str) -> Incident | None:
    return next((i for i in incidents() if i.id == incident_id), None)


def page(
    limit: int = 50, offset: int = 0, kind: str | None = None, q: str | None = None,
    severity: str | None = None,
) -> dict[str, object]:
    """A page of past incidents, newest first, optionally of one kind (`kev`, `breach`), one
    severity, or matching words in their statement."""
    found = list(incidents())
    if kind:
        found = [i for i in found if i.id.startswith(f"{PREFIX}{kind.upper()}-")]
    if severity:
        found = [i for i in found if str(i.severity) == severity]
    if q:
        words = q.lower().split()
        found = [
            i for i in found
            if all(w in (i.id + " " + " ".join(h.statement for h in i.hypotheses)).lower() for w in words)
        ]
    limit = max(1, min(limit, 200))
    return {
        "total": len(found),
        "offset": offset,
        "limit": limit,
        "generated": _data().get("generated"),
        "items": [i.model_dump(mode="json") for i in found[offset : offset + limit]],
    }
