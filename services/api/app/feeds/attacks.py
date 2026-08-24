"""Attacks that actually happened, from four public sources.

The feeds in `sources.py` publish *indicators* — a CVE being exploited, a URL
serving malware. These publish **incidents**: a named company named by the group
that breached it, a botnet controller answering right now, a breach somebody
disclosed. That is the difference the owner asked for on 24 August 2026, and it
is the difference between intelligence about the world and a scripted scenario.

Four rules specific to this file, on top of the package's three.

**A leak-site claim is the attacker's word.** Ransomware groups post victims to
pressure a payment. Some listings are inflated, a few are invented, and many are
never confirmed by the victim. Every one of these is `reported`, and the summary
says who is doing the claiming. Treating a criminal's press release as
`confirmed` because it arrived through a reputable aggregator is exactly the
mistake `Verification` exists to prevent.

**Nothing links to a leak site.** `claim_url` on a ransomware.live record is a
Tor address serving stolen data. This site links to ransomware.live's own
clearnet page for the group instead — a reader can still check the claim, and
the console never hands anybody a route to the stolen material.

**No causal chain is invented.** These records say *that* it happened and to
whom. They say nothing whatever about how, and constructing three plausible
steps and a remediation plan for a stranger's breach would be fabrication with a
technique id stapled to it. Reported attacks are events with provenance, and
that is deliberately all they are.

**A group's tradecraft is a fact about the group.** Not about this intrusion.
Nothing here attributes a technique to a specific victim.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from pashupatastra.events import (
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Provenance,
    SecurityPayload,
    Severity,
)

from . import Verification
from .sources import FeedUnavailable, USER_AGENT, _now

TIMEOUT = 45.0

RANSOMWARE_URL = "https://api.ransomware.live/v2/recentvictims"
FEODO_URL = "https://feodotracker.abuse.ch/downloads/ipblocklist.json"
THREATFOX_URL = "https://threatfox.abuse.ch/export/json/recent/"
HIBP_URL = "https://haveibeenpwned.com/api/v3/breaches"

RANSOMWARE_GROUP_PAGE = "https://www.ransomware.live/group/"


def _get(url: str) -> Any:
    """One GET, decoded as JSON.

    Duplicated from `sources.py` rather than imported as a private name, because
    a shared `_get` that grew a per-feed timeout or a per-feed retry would grow
    it for feeds that did not ask.
    """
    request = urllib.request.Request(url, headers={"user-agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise FeedUnavailable(f"{url}: {error}") from error


def _stamp(value: Any) -> datetime | None:
    """Publisher timestamps, in the several shapes the publishers send them.

    Returns `None` rather than `now()` on a value it cannot read. A record whose
    date is unparseable is dropped, because dating it to the moment it was
    fetched would present a two-year-old breach as something that happened this
    afternoon — and every one of these feeds is read as a timeline.
    """
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    for parse in (
        lambda t: datetime.fromisoformat(t),
        lambda t: datetime.strptime(t, "%Y-%m-%d %H:%M:%S"),
        lambda t: datetime.strptime(t, "%Y-%m-%d"),
    ):
        try:
            parsed = parse(text)
        except (TypeError, ValueError):
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _clean(value: Any, limit: int) -> str:
    """Publisher prose, trimmed. Some ransomware.live descriptions are marked
    `[AI generated]` by the publisher and a few are the literal string `N/A`."""
    text = str(value or "").strip()
    return "" if text.upper() == "N/A" else text[:limit]


# --- ransomware.live: victims named on leak sites ----------------------------


def fetch_ransomware(limit: int = 25, since: str | None = None) -> list[Event]:
    """Companies a ransomware group has publicly claimed to have breached.

    The closest thing to a real incident that exists in a free public feed: a
    named victim, a named group, a date, a sector and a country. It is also the
    one that most needs its verification label respected, because the source of
    the claim is the attacker.
    """
    rows = _get(RANSOMWARE_URL)
    if not isinstance(rows, list):
        raise FeedUnavailable(f"{RANSOMWARE_URL}: expected a list")

    ordered = sorted(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: str(row.get("discovered") or row.get("attackdate") or ""),
        reverse=True,
    )

    events: list[Event] = []
    for row in ordered:
        offset = str(row.get("discovered") or row.get("attackdate") or "")
        if since is not None and offset <= since:
            break
        victim = _clean(row.get("victim"), 160)
        group = _clean(row.get("group"), 60)
        occurred = _stamp(row.get("attackdate")) or _stamp(row.get("discovered"))
        if not victim or not group or occurred is None:
            continue

        sector = _clean(row.get("activity"), 80)
        country = _clean(row.get("country"), 8)

        events.append(
            Event(
                event_class=EventClass.SECURITY,
                source="ransomware-live",
                occurred_at=occurred,
                observed_at=_now(),
                entity_ref=EntityRef(
                    kind=EntityKind.ORGANISATION,
                    id=f"victim:{victim.lower()}",
                    name=victim,
                ),
                severity=Severity.CRITICAL,
                payload=SecurityPayload(
                    detection_type="ransomware_leak_site_claim",
                    asset=sector or None,
                    # Halfway, and not higher. The claim is credible enough to
                    # publish and uncorroborated enough that the victim may
                    # never confirm it.
                    confidence=0.5,
                ),
                provenance=Provenance(
                    source_system="ransomware-live",
                    # The group's page on ransomware.live — never `claim_url`,
                    # which is the Tor site hosting the stolen data.
                    url=f"{RANSOMWARE_GROUP_PAGE}{group}",
                    offset=offset,
                ),
                labels={
                    "verification": Verification.REPORTED,
                    "title": f"{group} claims a breach of {victim}",
                    "summary": (
                        _clean(row.get("description"), 400)
                        or f"Listed by {group} on its leak site. "
                        f"No confirmation from {victim}."
                    ),
                    "group": group,
                    "sector": sector,
                    "country": country,
                    "claimed_by": "the attacker",
                },
            )
        )
        if len(events) >= limit:
            break
    return events


# --- abuse.ch Feodo Tracker: botnet controllers answering now ----------------


def fetch_feodo(limit: int = 25, since: str | None = None) -> list[Event]:
    """Command-and-control servers for Emotet, QakBot, Dridex and friends.

    `corroborated` rather than `reported`: abuse.ch curates this tracker and
    lists a host only while it is observed serving as a controller, which is a
    stronger claim than a community submission and a weaker one than CISA
    stating a vulnerability is exploited in the wild.

    These are live, hostile addresses. They are stored as indicators keyed by
    address and are never rendered as links.
    """
    rows = _get(FEODO_URL)
    if not isinstance(rows, list):
        raise FeedUnavailable(f"{FEODO_URL}: expected a list")

    ordered = sorted(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: str(row.get("first_seen_utc") or ""),
        reverse=True,
    )

    events: list[Event] = []
    for row in ordered:
        address = _clean(row.get("ip_address"), 64)
        if not address:
            continue
        offset = f"{row.get('first_seen_utc') or ''}|{address}"
        if since is not None and offset <= since:
            continue

        malware = _clean(row.get("malware"), 60) or "unknown family"
        port = row.get("port")
        online = str(row.get("status", "")).lower() == "online"
        # `first_seen_utc` is frequently null on this feed. Falling back to now
        # would be a lie about when the controller appeared, so the event is
        # dated to now and the label says the publisher did not say.
        first_seen = _stamp(row.get("first_seen_utc"))

        events.append(
            Event(
                event_class=EventClass.SECURITY,
                source="feodo-tracker",
                occurred_at=first_seen or _now(),
                observed_at=_now(),
                entity_ref=EntityRef(
                    kind=EntityKind.INDICATOR,
                    id=f"ip:{address}",
                    name=address,
                ),
                severity=Severity.CRITICAL if online else Severity.WARNING,
                payload=SecurityPayload(
                    detection_type="botnet_command_and_control",
                    asset=_clean(row.get("as_name"), 120) or None,
                    confidence=0.8,
                ),
                provenance=Provenance(
                    source_system="feodo-tracker",
                    url=f"https://feodotracker.abuse.ch/browse/host/{address}/",
                    offset=offset,
                ),
                labels={
                    "verification": Verification.CORROBORATED,
                    "title": f"{malware} command-and-control at {address}",
                    "summary": (
                        f"{malware} controller on port {port}, hosted by "
                        f"{_clean(row.get('as_name'), 100) or 'an unnamed network'}"
                        f" (AS{row.get('as_number', '?')}). Status {row.get('status', 'unknown')}."
                    )[:400],
                    "malware": malware,
                    "port": str(port or ""),
                    "status": str(row.get("status", "")),
                    "first_seen": str(row.get("first_seen_utc") or "not stated by the publisher"),
                },
            )
        )
        if len(events) >= limit:
            break
    return events


# --- abuse.ch ThreatFox: indicators from live campaigns ----------------------


def fetch_threatfox(limit: int = 25, since: str | None = None) -> list[Event]:
    """Indicators tied to a named malware family, from the bulk export.

    The ThreatFox *API* requires a key, which is why an earlier note in
    `sources.py` said the feed was unavailable. The **bulk export** used here
    does not, and was verified returning 3.9 MB unauthenticated on 24 August
    2026.

    Most submissions are anonymous, so most are `reported`. A named reporter at
    full confidence earns `corroborated` and nothing earns `confirmed` — the
    publisher does not assert these individually.
    """
    payload = _get(THREATFOX_URL)
    if not isinstance(payload, dict):
        raise FeedUnavailable(f"{THREATFOX_URL}: expected an object")

    rows: list[dict] = []
    for group in payload.values():
        # Each id maps to a single-element list.
        for row in group or []:
            if isinstance(row, dict):
                rows.append(row)
    rows.sort(key=lambda row: str(row.get("first_seen_utc") or ""), reverse=True)

    events: list[Event] = []
    for row in rows:
        offset = str(row.get("first_seen_utc") or "")
        if since is not None and offset <= since:
            break
        value = _clean(row.get("ioc_value"), 200)
        occurred = _stamp(row.get("first_seen_utc"))
        if not value or occurred is None:
            continue

        family = _clean(row.get("malware_printable"), 60) or _clean(row.get("malware"), 60)
        reporter = _clean(row.get("reporter"), 60) or "anonymous"
        confidence = row.get("confidence_level")
        try:
            confidence = int(confidence)
        except (TypeError, ValueError):
            confidence = 0

        trusted = confidence >= 100 and reporter != "anonymous"
        ioc_type = _clean(row.get("ioc_type"), 40) or "indicator"

        events.append(
            Event(
                event_class=EventClass.SECURITY,
                source="threatfox",
                occurred_at=occurred,
                observed_at=_now(),
                entity_ref=EntityRef(
                    kind=EntityKind.INDICATOR,
                    id=f"{ioc_type}:{value}",
                    name=value,
                ),
                severity=Severity.WARNING if confidence >= 75 else Severity.INFO,
                payload=SecurityPayload(
                    detection_type=_clean(row.get("threat_type"), 60) or "malware_indicator",
                    asset=family or None,
                    confidence=min(max(confidence / 100, 0.0), 1.0),
                ),
                provenance=Provenance(
                    source_system="threatfox",
                    url="https://threatfox.abuse.ch/browse/",
                    offset=offset,
                ),
                labels={
                    "verification": (
                        Verification.CORROBORATED if trusted else Verification.REPORTED
                    ),
                    "title": f"{family or 'Malware'} indicator: {ioc_type}",
                    "summary": (
                        f"{_clean(row.get('threat_type'), 60) or 'indicator'} for "
                        f"{family or 'an unnamed family'}, reported by {reporter} "
                        f"at {confidence}% confidence."
                    )[:400],
                    "malware": family,
                    "ioc_type": ioc_type,
                    "tags": _clean(row.get("tags"), 200),
                    "reporter": reporter,
                },
            )
        )
        if len(events) >= limit:
            break
    return events


# --- Have I Been Pwned: disclosed breaches -----------------------------------


def fetch_hibp(limit: int = 25, since: str | None = None) -> list[Event]:
    """Breaches that have been disclosed and loaded into HIBP.

    Ordered by `AddedDate` — when HIBP published it — not `BreachDate`. The two
    are often years apart, and a timeline built on the breach date would show
    today's disclosure of a 2023 incident as nothing at all.

    HIBP marks records it has validated. `IsVerified` earns `corroborated`;
    anything flagged `IsFabricated` is dropped rather than published with a
    caveat, since the publisher is saying the data is not real.
    """
    rows = _get(HIBP_URL)
    if not isinstance(rows, list):
        raise FeedUnavailable(f"{HIBP_URL}: expected a list")

    ordered = sorted(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: str(row.get("AddedDate") or ""),
        reverse=True,
    )

    events: list[Event] = []
    for row in ordered:
        offset = str(row.get("AddedDate") or "")
        if since is not None and offset <= since:
            break
        if row.get("IsFabricated"):
            continue
        name = _clean(row.get("Title") or row.get("Name"), 160)
        # Dated to the **disclosure**, not to the breach.
        #
        # The event being recorded is "this breach was published", which is what
        # happened today; the breach itself may be from 2023 and is carried as a
        # label. Dating the event to `BreachDate` sorted every one of these off
        # the end of a timeline built on recency — HIBP had twelve records
        # stored and none of them reached the page.
        occurred = _stamp(row.get("AddedDate")) or _stamp(row.get("BreachDate"))
        if not name or occurred is None:
            continue

        count = row.get("PwnCount") or 0
        verified = bool(row.get("IsVerified"))
        classes = row.get("DataClasses") or []

        events.append(
            Event(
                event_class=EventClass.SECURITY,
                source="hibp",
                occurred_at=occurred,
                observed_at=_now(),
                entity_ref=EntityRef(
                    kind=EntityKind.ORGANISATION,
                    id=f"breach:{_clean(row.get('Name'), 80).lower()}",
                    name=name,
                ),
                severity=Severity.CRITICAL if count >= 1_000_000 else Severity.WARNING,
                payload=SecurityPayload(
                    detection_type="disclosed_data_breach",
                    asset=_clean(row.get("Domain"), 120) or None,
                    confidence=0.9 if verified else 0.4,
                ),
                provenance=Provenance(
                    source_system="hibp",
                    url=_clean(row.get("DisclosureUrl"), 400)
                    or f"https://haveibeenpwned.com/PwnedWebsites#{_clean(row.get('Name'), 80)}",
                    offset=offset,
                ),
                labels={
                    "verification": (
                        Verification.CORROBORATED if verified else Verification.REPORTED
                    ),
                    "title": f"{name}: {count:,} accounts exposed",
                    "summary": (
                        f"Breach occurred {str(row.get('BreachDate', 'unknown'))[:10]}, "
                        f"published by HIBP {str(row.get('AddedDate', ''))[:10]}. "
                        f"Exposed: {', '.join(str(c) for c in classes[:6])}."
                    )[:400],
                    "accounts": str(count),
                    "exposed": ", ".join(str(c) for c in classes[:8])[:200],
                    "breach_date": str(row.get("BreachDate", "")),
                    # Deliberately not `status`. That label means "is this
                    # thing still up" for URLhaus and Feodo, and the grouping
                    # code reads it to decide whether an indicator is live.
                    # Putting "verified" there filed every disclosed breach as
                    # dead infrastructure.
                    "confirmation": "verified by HIBP" if verified else "unverified",
                },
            )
        )
        if len(events) >= limit:
            break
    return events


ATTACK_FEEDS = {
    "ransomware-live": fetch_ransomware,
    "feodo-tracker": fetch_feodo,
    "threatfox": fetch_threatfox,
    "hibp": fetch_hibp,
}
