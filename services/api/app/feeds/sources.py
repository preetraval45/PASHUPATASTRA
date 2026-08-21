"""The feeds themselves: fetch, and turn each entry into an `Event`.

Two are here. A third, ThreatFox, is deliberately absent — abuse.ch now requires
an API key for it, and a key nobody has is a dependency that fails in
production and passes in every test written around it.

No SDK, no client library. Each of these is one GET returning JSON, and a
library would add a dependency to the Lambda bundle, a second retry policy, and
a vendor name in a module whose whole job is to be replaceable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, Iterable

from pashupatastra.events import (
    Event,
    EventClass,
    EntityKind,
    EntityRef,
    Provenance,
    SecurityPayload,
    Severity,
)

from . import Verification

USER_AGENT = "pashupatastra/0.1 (+https://pashupatastra.vercel.app)"
TIMEOUT = 45.0

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
URLHAUS_URL = "https://urlhaus.abuse.ch/downloads/json_recent/"


class FeedUnavailable(RuntimeError):
    """The feed did not answer. Never fatal — one feed being down is not a
    reason to skip the others, and the scheduler will come round again."""


def _get(url: str) -> Any:
    request = urllib.request.Request(url, headers={"user-agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise FeedUnavailable(f"{url}: {error}") from error


def _now() -> datetime:
    return datetime.now(UTC)


# --- CISA Known Exploited Vulnerabilities ------------------------------------


def fetch_kev(limit: int = 25, since: str | None = None) -> list[Event]:
    """Vulnerabilities CISA has observed being exploited.

    `confirmed`, and it is the only source here that earns it: the catalogue's
    entry criterion is evidence of active exploitation, not a report of a
    weakness. That is also why this is worth ingesting at all — a CVE feed lists
    what could be attacked, and this lists what is being.

    The catalogue is not in date order — the last entries in the file are from
    2021 — so "recent" means sorting by `dateAdded` rather than taking the tail.
    Ingesting all 1,600 on the first run would be a wall of five-year-old
    advisories presented as news.
    """
    payload = _get(KEV_URL)
    entries: Iterable[dict] = payload.get("vulnerabilities") or []
    ordered = sorted(entries, key=lambda entry: entry.get("dateAdded", ""), reverse=True)

    events: list[Event] = []
    for entry in ordered:
        added = entry.get("dateAdded", "")
        if since is not None and added <= since:
            break
        cve = entry.get("cveID")
        if not cve:
            continue

        occurred = _parse_day(added)
        ransomware = str(entry.get("knownRansomwareCampaignUse", "")).lower() == "known"
        events.append(
            Event(
                event_class=EventClass.SECURITY,
                source="cisa-kev",
                occurred_at=occurred,
                observed_at=_now(),
                entity_ref=EntityRef(kind=EntityKind.VULNERABILITY, id=cve, name=cve),
                # Ransomware use is the field that decides whether this is
                # urgent or merely important, so it decides the severity here
                # rather than being left in the payload for a reader to notice.
                severity=Severity.CRITICAL if ransomware else Severity.WARNING,
                payload=SecurityPayload(
                    detection_type="known_exploited_vulnerability",
                    asset=f"{entry.get('vendorProject', '')} {entry.get('product', '')}".strip(),
                    confidence=1.0,
                ),
                provenance=Provenance(
                    source_system="cisa-kev",
                    url=f"https://nvd.nist.gov/vuln/detail/{cve}",
                    offset=added,
                ),
                labels={
                    "verification": Verification.CONFIRMED,
                    "title": str(entry.get("vulnerabilityName", ""))[:200],
                    "summary": str(entry.get("shortDescription", ""))[:400],
                    "required_action": str(entry.get("requiredAction", ""))[:300],
                    "due_date": str(entry.get("dueDate", "")),
                    "ransomware": "known" if ransomware else "unknown",
                },
            )
        )
        if len(events) >= limit:
            break
    return events


# --- abuse.ch URLhaus --------------------------------------------------------


def fetch_urlhaus(limit: int = 25, since: str | None = None) -> list[Event]:
    """URLs submitted as distributing malware.

    `reported`, always. These are community submissions; abuse.ch publishes them
    without asserting each one, and labelling them `confirmed` because they
    arrived from a reputable aggregator is exactly the mistake `Verification`
    exists to prevent.

    The URL itself is *not* stored in the entity name or reachable as a link
    from the console. These are live malware distribution points, and a page
    that renders them as anchors is a page that eventually gets clicked. The
    `urlhaus_link` — the advisory *about* the URL — is what a reader follows.
    """
    payload = _get(URLHAUS_URL)
    rows: list[dict] = []
    for group in (payload or {}).values():
        rows.extend(group or [])
    rows.sort(key=lambda row: row.get("dateadded", ""), reverse=True)

    events: list[Event] = []
    for row in rows:
        added = row.get("dateadded", "")
        if since is not None and added <= since:
            break
        url = row.get("url")
        if not url:
            continue

        host = _host_of(url)
        events.append(
            Event(
                event_class=EventClass.SECURITY,
                source="urlhaus",
                occurred_at=_parse_stamp(added),
                observed_at=_now(),
                entity_ref=EntityRef(
                    kind=EntityKind.INDICATOR,
                    # Keyed by host, not by the full URL: a key is rendered in
                    # places a full malware URL should not appear, and one host
                    # serving forty payloads is one indicator, not forty.
                    id=f"url:{host}",
                    name=host,
                ),
                severity=(
                    Severity.WARNING if row.get("url_status") == "online" else Severity.INFO
                ),
                payload=SecurityPayload(
                    detection_type=str(row.get("threat", "malware_download")),
                    # A community report, and the number says so. Rating an
                    # unreviewed submission higher would put it alongside CISA's
                    # confirmed exploitation in every ranking that reads this.
                    confidence=0.5,
                ),
                provenance=Provenance(
                    source_system="urlhaus",
                    url=str(row.get("urlhaus_link", "")) or None,
                    offset=added,
                ),
                labels={
                    "verification": Verification.REPORTED,
                    "title": f"Malware distribution reported at {host}",
                    "summary": (
                        f"{row.get('threat', 'malware')} reported by "
                        f"{row.get('reporter', 'anonymous')}; "
                        f"status {row.get('url_status', 'unknown')}"
                    )[:400],
                    "tags": ", ".join(_tags(row))[:200],
                    "status": str(row.get("url_status", "")),
                },
            )
        )
        if len(events) >= limit:
            break
    return events


# --- parsing helpers ---------------------------------------------------------


def _parse_day(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return _now()


def _parse_stamp(value: str) -> datetime:
    for pattern in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    return _now()


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    try:
        return urlparse(url).hostname or "unknown"
    except ValueError:
        return "unknown"


def _tags(row: dict) -> list[str]:
    """URLhaus sends tags as a JSON list, sometimes as a Python-repr string."""
    raw = row.get("tags")
    if isinstance(raw, list):
        return [str(tag) for tag in raw]
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw.replace("'", '"'))
            return [str(tag) for tag in parsed] if isinstance(parsed, list) else [raw]
        except json.JSONDecodeError:
            return [raw]
    return []


FEEDS = {"cisa-kev": fetch_kev, "urlhaus": fetch_urlhaus}
