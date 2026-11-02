"""Incidents from what is happening in the world right now, built from the feeds already stored.

The console used to open on written scenarios. These are real: each incident below is derived
from records the scheduled poll stored from CISA, NIST, abuse.ch, ransomware.live and Have I
Been Pwned, cites those records by id (rule 1), and links the publisher's own page. Nothing is
invented to make one look complete: no affected users, no topology, no blast radius that a feed
did not state.

Five kinds, each a rule a reader can check against the source:

- **Actively exploited** — every CVE CISA added to its Known Exploited Vulnerabilities catalogue
  in the last 30 days. Critical when CISA records ransomware use.
- **Critical disclosure** — every CVE NVD published in the last 7 days with a CVSS score of 9.0
  or more. Reported, not known to be exploited, and said so.
- **Botnet infrastructure** — a malware family with at least `C2_MIN` new command-and-control
  indicators reported to ThreatFox or Feodo Tracker in the last 24 hours.
- **Ransomware campaign** — a group claiming at least `RW_MIN` victims on its leak site in the
  last 72 hours. Victims are counted by sector and country, never named here: the claim is the
  attacker's, and repeating names is publishing the extortion.
- **Data breach** — a breach Have I Been Pwned published in the last 30 days.

They are derived, not stored: a pure function of the event store, rebuilt at most every
`CACHE_SECONDS` per process. An incident leaves the list when its window passes, so there is no
stale copy to clean up and no second answer to disagree with the feeds.
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from pashupatastra import (
    CausalLink,
    EntityKind,
    EntityRef,
    Hypothesis,
    Incident,
    IncidentSeverity,
    IncidentState,
    PlanStep,
)
from pashupatastra.defang import defang
from pashupatastra.incidents import Source, Transition
from pashupatastra.registry import get as get_action

PREFIX = "LIVE-"
PUBLISHERS = {"threatfox": "ThreatFox", "feodo-tracker": "Feodo Tracker"}
CACHE_SECONDS = 600
C2_MIN = 5
RW_MIN = 3
MAX_EVIDENCE = 25

KEV_DAYS = 30
NVD_DAYS = 7
NVD_CRITICAL = 9.0
C2_HOURS = 24
RW_HOURS = 72
BREACH_DAYS = 30

LIMITS = {
    "cisa-kev": 100,
    "nvd": 300,
    "threatfox": 300,
    "feodo-tracker": 100,
    "ransomware-live": 300,
    "hibp": 50,
}
"""How far back each source is read: the recent index holds up to 300 per source."""


def is_live(incident_id: str) -> bool:
    return incident_id.startswith(PREFIX)


def _when(row: dict) -> datetime | None:
    value = row.get("occurred_at")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "unknown"


def _plan(*action_ids: str) -> list[PlanStep]:
    return [
        PlanStep(
            order=order,
            action_id=action_id,
            expected_post_state=get_action(action_id).expected_post_state,
            rollback_action_id=get_action(action_id).rollback_action_id,
        )
        for order, action_id in enumerate(action_ids, start=1)
    ]


def _opened(at: datetime, by: str) -> list[Transition]:
    return [Transition(at=at, from_state=None, to_state=IncidentState.DETECTED, actor=by,
                       justification="derived from the stored feed records it cites")]


def _source(row: dict, title: str, publisher: str) -> list[Source]:
    url = (row.get("provenance") or {}).get("url") or ""
    return [Source(title=title[:200], url=url, publisher=publisher)] if url.startswith("https://") else []


# --- the five rules -------------------------------------------------------------------------------


def _kev(rows: list[dict], now: datetime, days: int | None = KEV_DAYS, prefix: str = PREFIX) -> list[Incident]:
    out = []
    for row in rows:
        at = _when(row)
        cve = (row.get("entity_key") or "").removeprefix("vulnerability:")
        if at is None or not cve or (days is not None and now - at > timedelta(days=days)):
            continue
        labels = row.get("labels") or {}
        ransomware = labels.get("ransomware") == "known"
        entity = EntityRef(kind=EntityKind.VULNERABILITY, id=cve, name=cve)
        due = labels.get("due_date")
        out.append(Incident(
            id=f"{prefix}KEV-{cve}",
            severity=IncidentSeverity.CRITICAL if ransomware else IncidentSeverity.HIGH,
            opened_at=at,
            affected_entities=[entity],
            event_ids=[row["id"]],
            hypotheses=[Hypothesis(
                statement=(
                    f"{cve} ({labels.get('title', 'unnamed')}) is being exploited in the wild: CISA added it "
                    f"to the Known Exploited Vulnerabilities catalogue"
                    + (f", with federal remediation due {due}" if due else "")
                    + (", and records its use in ransomware campaigns." if ransomware else ".")
                ),
                confidence=0.95,
                evidence=[row["id"]],
            )],
            causal_chain=[CausalLink(entity=entity, transition="observed exploited in the wild", evidence=[row["id"]])],
            plan=_plan("query_threat_intel", "create_case", "notify_analyst"),
            transitions=_opened(at, "drishti:cisa-kev"),
            sources=_source(row, f"{cve} on NVD", "CISA KEV / NIST NVD"),
        ))
    return out


def _nvd(rows: list[dict], now: datetime) -> list[Incident]:
    out = []
    for row in rows:
        at = _when(row)
        labels = row.get("labels") or {}
        cve = (row.get("entity_key") or "").removeprefix("vulnerability:")
        try:
            score = float(labels.get("cvss") or 0)
        except ValueError:
            score = 0.0
        if at is None or not cve or score < NVD_CRITICAL or now - at > timedelta(days=NVD_DAYS):
            continue
        entity = EntityRef(kind=EntityKind.VULNERABILITY, id=cve, name=cve)
        out.append(Incident(
            id=f"{PREFIX}NVD-{cve}",
            severity=IncidentSeverity.HIGH,
            opened_at=at,
            affected_entities=[entity],
            event_ids=[row["id"]],
            hypotheses=[Hypothesis(
                statement=(
                    f"{cve} was disclosed with CVSS {score:.1f} ({labels.get('cvss_severity', 'critical').lower()}): "
                    f"{labels.get('summary', '')[:240]} Reported, not yet known to be exploited."
                ),
                confidence=0.6,
                evidence=[row["id"]],
            )],
            causal_chain=[CausalLink(entity=entity, transition="disclosed as critical", evidence=[row["id"]])],
            plan=_plan("query_threat_intel", "notify_analyst"),
            transitions=_opened(at, "drishti:nvd"),
            sources=_source(row, f"{cve} on NVD", "NIST NVD"),
        ))
    return out


def _c2(rows: list[dict], now: datetime) -> list[Incident]:
    families: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        at = _when(row)
        family = (row.get("labels") or {}).get("malware")
        if at is not None and family and now - at <= timedelta(hours=C2_HOURS):
            families[family].append(row)
    out = []
    for family, found in families.items():
        if len(found) < C2_MIN:
            continue
        found.sort(key=lambda r: r["occurred_at"], reverse=True)
        cited = [r["id"] for r in found[:MAX_EVIDENCE]]
        # Defanged in the incident itself, not only when rendered: these are live malicious
        # addresses, and every page, export and chat answer that repeats them must not make them
        # something a reader can click.
        entities = [
            EntityRef(kind=EntityKind.INDICATOR, id=defang(r["entity_key"].removeprefix("indicator:")),
                      name=defang(r["entity_key"].removeprefix("indicator:")))
            for r in found[:10] if r.get("entity_key")
        ]
        first = min(_when(r) for r in found)
        sources = Counter(r["source"] for r in found)
        out.append(Incident(
            id=f"{PREFIX}C2-{_slug(family)}-{now:%Y%m%d}",
            severity=IncidentSeverity.HIGH if len(found) >= 20 else IncidentSeverity.MEDIUM,
            opened_at=first,
            affected_entities=entities,
            event_ids=cited,
            hypotheses=[Hypothesis(
                statement=(
                    f"{family} infrastructure is active: {len(found)} new indicators in the last {C2_HOURS} hours "
                    f"({', '.join(f'{n} from {PUBLISHERS.get(s, s)}' for s, n in sources.most_common())})."
                ),
                confidence=0.7,
                evidence=cited,
            )],
            causal_chain=[CausalLink(entity=e, transition=f"reported as {family} infrastructure", evidence=[cid])
                          for e, cid in zip(entities, cited)],
            plan=_plan("query_threat_intel", "block_ip", "notify_analyst"),
            transitions=_opened(first, "drishti:" + "+".join(sorted(sources))),
            sources=_source(found[0], f"{family} on {found[0]['source']}", "abuse.ch"),
        ))
    return out


def _ransomware(rows: list[dict], now: datetime) -> list[Incident]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        at = _when(row)
        group = (row.get("labels") or {}).get("group")
        if at is not None and group and now - at <= timedelta(hours=RW_HOURS):
            groups[group].append(row)
    out = []
    for group, found in groups.items():
        if len(found) < RW_MIN:
            continue
        found.sort(key=lambda r: r["occurred_at"], reverse=True)
        cited = [r["id"] for r in found[:MAX_EVIDENCE]]
        sectors = Counter((r.get("labels") or {}).get("sector") or "unstated" for r in found)
        countries = Counter((r.get("labels") or {}).get("country") or "unstated" for r in found)
        actor = EntityRef(kind=EntityKind.ORGANISATION, id=f"group:{group}", name=group)
        first = min(_when(r) for r in found)
        out.append(Incident(
            id=f"{PREFIX}RW-{_slug(group)}-{now:%Y%m%d}",
            severity=IncidentSeverity.HIGH,
            opened_at=first,
            affected_entities=[actor],
            event_ids=cited,
            hypotheses=[Hypothesis(
                statement=(
                    f"The {group} ransomware group claimed {len(found)} victims in the last {RW_HOURS} hours. "
                    f"Sectors: {', '.join(f'{s} {n}' for s, n in sectors.most_common(4))}. "
                    f"Countries: {', '.join(f'{c} {n}' for c, n in countries.most_common(4))}. "
                    "Claims are the attacker's own and unverified."
                ),
                confidence=0.5,
                evidence=cited,
            )],
            causal_chain=[CausalLink(entity=actor, transition="claiming victims on its leak site", evidence=cited[:5])],
            plan=_plan("query_threat_intel", "notify_analyst"),
            transitions=_opened(first, "drishti:ransomware-live"),
            sources=[Source(title=f"{group} on ransomware.live", url=f"https://www.ransomware.live/group/{_slug(group)}",
                            publisher="ransomware.live")],
        ))
    return out


def _breaches(rows: list[dict], now: datetime, days: int | None = BREACH_DAYS, prefix: str = PREFIX) -> list[Incident]:
    out = []
    for row in rows:
        at = _when(row)
        if at is None or (days is not None and now - at > timedelta(days=days)):
            continue
        labels = row.get("labels") or {}
        name = (row.get("entity_key") or "").removeprefix("organisation:breach:")
        try:
            accounts = int(labels.get("accounts") or 0)
        except ValueError:
            accounts = 0
        entity = EntityRef(kind=EntityKind.ORGANISATION, id=f"breach:{name}", name=labels.get("title", name))
        out.append(Incident(
            id=f"{prefix}BREACH-{_slug(name)}",
            severity=IncidentSeverity.HIGH if accounts >= 1_000_000 else IncidentSeverity.MEDIUM,
            opened_at=at,
            affected_entities=[entity],
            event_ids=[row["id"]],
            hypotheses=[Hypothesis(
                statement=f"{labels.get('title', name)}. Exposed: {labels.get('exposed', 'not stated')}.",
                confidence=0.9,
                evidence=[row["id"]],
            )],
            causal_chain=[CausalLink(entity=entity, transition="accounts exposed in a breach", evidence=[row["id"]])],
            plan=_plan("query_threat_intel", "notify_analyst"),
            transitions=_opened(at, "drishti:hibp"),
            sources=_source(row, labels.get("title", name), "Have I Been Pwned"),
        ))
    return out


RULES = {
    "cisa-kev": _kev,
    "nvd": _nvd,
    "threatfox": _c2,
    "ransomware-live": _ransomware,
    "hibp": _breaches,
}


def build(store, now: datetime | None = None) -> list[Incident]:
    """Every live incident the stored records support, newest first."""
    now = now or datetime.now(UTC)
    incidents: list[Incident] = []
    for source, rule in RULES.items():
        sources = [source, "feodo-tracker"] if rule is _c2 else [source]
        try:
            rows = [row for s in sources for row in store.recent_events(sources=[s], limit=LIMITS[s])]
        except Exception:  # noqa: BLE001 - one unreadable source must not empty the page
            continue
        incidents.extend(rule(rows, now))
    incidents.sort(key=lambda i: i.opened_at, reverse=True)
    return incidents


_cache: dict[str, object] = {"at": 0.0, "incidents": []}


def current(store) -> list[Incident]:
    """`build`, at most once every `CACHE_SECONDS` in this process."""
    if time.monotonic() - float(_cache["at"]) > CACHE_SECONDS or not _cache["incidents"]:
        _cache["incidents"] = build(store)
        _cache["at"] = time.monotonic()
    return list(_cache["incidents"])  # type: ignore[arg-type]
