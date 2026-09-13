"""The feeds themselves: fetch, and turn each entry into an `Event`.

Three are here: CISA KEV, URLhaus, and NVD's recent disclosures (R76). The
real-attack feeds — leak sites, Feodo, ThreatFox, HIBP — are in `attacks.py`.

**AlienVault OTX is deliberately absent.** R76 named it beside NVD, and the
pulse endpoints all require an account's API key — a key nobody has is a
dependency that fails in production and passes in every test written around
it, which is the same reason ThreatFox was left out until a keyless export
existed. If OTX ever publishes one, it belongs here; until then it is not
half-wired.

No SDK, no client library. Each of these is one GET returning JSON, and a
library would add a dependency to the Lambda bundle, a second retry policy, and
a vendor name in a module whose whole job is to be replaceable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
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
NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


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


# --- NVD recent disclosures ---------------------------------------------------

NVD_FIRST_WINDOW_HOURS = 24
"""How far back the first poll looks. NVD publishes on the order of three
hundred CVEs a day; a first run that reached back a week would spend its
whole allowance on the oldest of two thousand."""


def _parse_iso(value: str) -> datetime:
    """NVD's `2026-09-10T19:17:32.423` — ISO, milliseconds, no offset, UTC.

    Its own parser rather than a pattern added to `_parse_stamp`, because
    that one falls back to *now* on a shape it does not know, and a cursor
    parsed as *now* would open an empty window on every poll and the feed
    would look quiet forever. A shape this feed cannot read is an error.
    """
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _nvd_stamp(value: datetime) -> str:
    """The API's own timestamp shape, to the millisecond, no offset — it takes
    UTC and rejects a `+00:00`. The milliseconds are real: a window that
    started at `.000` would re-fetch the cursor's own record every poll."""
    utc = value.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}"


def fetch_nvd(limit: int = 25, since: str | None = None) -> list[Event]:
    """CVEs published to NVD since the cursor, oldest first.

    **Reported, unless NVD has analysed it.** A CVE record is what its CNA
    published; NVD's own analysis — a CVSS score it assigned, `vulnStatus:
    Analyzed` — is the publisher's review, and only that earns `corroborated`.
    Most recent records are `Awaiting Analysis` or `Deferred`, and they stay
    `reported`, because "someone registered a CVE" is exactly what that word
    means. Nothing from this feed is ever `confirmed`: that is KEV's word for
    observed exploitation, and a disclosure is not an exploit.

    **The cursor walks forward through publication time.** The API returns a
    window oldest-first and there is no newest-first ordering, so each poll
    takes the next `limit` after the cursor rather than the head of the day;
    at twenty-five an hour against roughly three hundred a day the cursor
    keeps up, and if it ever fell behind the page would show that as a growing
    gap between `published` and now rather than skip silently. The window
    starts at the cursor's own timestamp plus one millisecond, so the last
    record stored is not fetched twice.

    Severity is NVD's CVSS `baseSeverity` where a metric exists, from the
    newest CVSS version present. Without one the record is `INFO`: a
    disclosure with no score is a disclosure, and guessing a severity for it
    would be the invented number every other feed here refuses.
    """
    end = _now()
    if since:
        start = _parse_iso(since) + timedelta(milliseconds=1)
    else:
        start = end - timedelta(hours=NVD_FIRST_WINDOW_HOURS)
    url = (
        f"{NVD_URL}?pubStartDate={_nvd_stamp(start)}&pubEndDate={_nvd_stamp(end)}"
        f"&resultsPerPage={max(1, min(limit, 200))}"
    )
    payload = _get(url)
    entries: Iterable[dict] = payload.get("vulnerabilities") or []

    events: list[Event] = []
    for entry in entries:
        cve = entry.get("cve") or {}
        identifier = cve.get("id")
        published = cve.get("published")
        if not identifier or not published:
            continue
        description = next(
            (d.get("value", "") for d in cve.get("descriptions") or [] if d.get("lang") == "en"),
            "",
        )
        score, severity_word, vector = _nvd_cvss(cve.get("metrics") or {})
        status = str(cve.get("vulnStatus", ""))
        analysed = status.lower() == "analyzed"
        events.append(
            Event(
                event_class=EventClass.SECURITY,
                source="nvd",
                occurred_at=_parse_iso(published),
                observed_at=_now(),
                entity_ref=EntityRef(kind=EntityKind.VULNERABILITY, id=identifier, name=identifier),
                severity=_nvd_severity(severity_word),
                payload=SecurityPayload(
                    detection_type="cve_disclosure",
                    asset=str(cve.get("sourceIdentifier", ""))[:120],
                    confidence=1.0,
                ),
                provenance=Provenance(
                    source_system="nvd",
                    url=f"https://nvd.nist.gov/vuln/detail/{identifier}",
                    offset=published,
                ),
                labels={
                    "verification": (
                        Verification.CORROBORATED if analysed else Verification.REPORTED
                    ),
                    "title": description[:200],
                    "summary": description[:400],
                    # Not `status`: URLhaus uses that key for online/offline
                    # and the page renders it as the URL's state.
                    "analysis": status,
                    "cvss": score,
                    "cvss_severity": severity_word,
                    "vector": vector,
                    "cna": str(cve.get("sourceIdentifier", ""))[:120],
                },
            )
        )
        if len(events) >= limit:
            break
    return events


def _nvd_cvss(metrics: dict) -> tuple[str, str, str]:
    """Score, severity word and vector from the newest CVSS version present."""
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for metric in metrics.get(key) or []:
            data = metric.get("cvssData") or {}
            if "baseScore" in data:
                severity = data.get("baseSeverity") or metric.get("baseSeverity") or ""
                return (
                    str(data.get("baseScore", "")),
                    str(severity).upper(),
                    str(data.get("vectorString", ""))[:200],
                )
    return "", "", ""


def _nvd_severity(word: str) -> Severity:
    """CVSS words onto the three the event model has. `MEDIUM` and `LOW` are
    `INFO` alongside "no score at all" — a disclosure is not an alert, and
    only the top of the CVSS scale is worth a colour on a page whose other
    entries are controllers answering right now."""
    if word == "CRITICAL":
        return Severity.CRITICAL
    if word == "HIGH":
        return Severity.WARNING
    return Severity.INFO


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


FEEDS = {"cisa-kev": fetch_kev, "urlhaus": fetch_urlhaus, "nvd": fetch_nvd}
