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
import re
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from pashupatastra import (
    CausalLink,
    EntityKind,
    EntityRef,
    Hypothesis,
    Incident,
    IncidentSeverity,
)
from pashupatastra.incidents import AttackTechnique, Source

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


def records() -> list[dict]:
    return _data().get("records") or []


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


def _ransomware_months(rows: list[dict]) -> list[Incident]:
    """One incident per ransomware group per month of the archive: how many victims it claimed."""
    out = []
    for row in rows:
        labels = row["labels"]
        group, month, claims = labels["group"], labels["month"], int(labels["claims"])
        actor = EntityRef(kind=EntityKind.ORGANISATION, id=f"group:{group}", name=group)
        out.append(Incident(
            id=f"{PREFIX}RW-{rules._slug(group)}-{month.replace('-', '')}",
            severity=IncidentSeverity.HIGH if claims >= 20 else IncidentSeverity.MEDIUM,
            opened_at=rules._when(row),
            affected_entities=[actor],
            event_ids=[row["id"]],
            hypotheses=[Hypothesis(
                statement=(f"The {group} ransomware group claimed {claims} victims on its leak site in {month}. "
                           "Claims are the attacker's own and unverified."),
                confidence=0.5,
                evidence=[row["id"]],
            )],
            causal_chain=[CausalLink(entity=actor, transition="claiming victims on its leak site", evidence=[row["id"]])],
            plan=rules._plan("query_threat_intel", "notify_analyst"),
            transitions=rules._opened(rules._when(row), "drishti:ransomwatch"),
            sources=[Source(title=f"{group} in the ransomwatch archive", url=row["provenance"]["url"],
                            publisher="ransomwatch (public domain)")],
        ))
    return out


def _campaigns(rows: list[dict]) -> list[Incident]:
    """MITRE ATT&CK's documented intrusion campaigns, each step a technique the campaign used."""
    out = []
    for row in rows:
        labels = row["labels"]
        when = rules._when(row)
        if when is None:
            continue
        actor_name = labels.get("group") or labels["name"]
        actor = EntityRef(kind=EntityKind.ORGANISATION, id=f"campaign:{labels['campaign']}", name=actor_name)
        chain = []
        for entry in filter(None, (labels.get("techniques") or "").split(";")):
            tid, name, tactic = (entry.split("|") + ["", ""])[:3]
            try:
                technique = AttackTechnique(id=tid, name=name, tactic=tactic or "unstated")
            except ValueError:
                continue
            chain.append(CausalLink(entity=actor, transition=f"used {name}", evidence=[row["id"]],
                                    attack_technique=technique))
        span = f"{labels.get('first_seen') or '?'} to {labels.get('last_seen') or '?'}"
        out.append(Incident(
            id=f"{PREFIX}CAMPAIGN-{labels['campaign']}",
            severity=IncidentSeverity.HIGH,
            opened_at=when,
            affected_entities=[actor],
            event_ids=[row["id"]],
            hypotheses=[Hypothesis(
                statement=(f"{labels['name']} ({labels['campaign']}), {span}"
                           + (f", attributed to {labels['group']}" if labels.get("group") else "")
                           + f": {rules._clip(labels.get('summary', ''), 400)}"),
                confidence=0.9,
                evidence=[row["id"]],
            )],
            causal_chain=chain[:40] or [CausalLink(entity=actor, transition="documented intrusion", evidence=[row["id"]])],
            plan=rules._plan("query_threat_intel", "notify_analyst"),
            transitions=rules._opened(when, "drishti:mitre-attack"),
            sources=[Source(title=f"{labels['name']} on MITRE ATT&CK", url=row["provenance"]["url"],
                            publisher="MITRE ATT&CK (© The MITRE Corporation)")],
        ))
    return out


def _builders(records: list[dict]) -> dict[str, object]:
    """Which rule builds each source's incidents, over the records old enough to be the past."""
    now = datetime.now(UTC)
    exploited = {r["entity_key"] for r in records if r["source"] == "cisa-kev"}
    return {
        "cisa-kev": lambda rows: rules._kev(rows, now, days=None, prefix=PREFIX),
        "hibp": lambda rows: rules._breaches(rows, now, days=None, prefix=PREFIX),
        # A disclosure CISA later confirmed exploited is listed once, as exploited.
        "nvd": lambda rows: rules._nvd([r for r in rows if r["entity_key"] not in exploited],
                                       now, days=None, prefix=PREFIX),
        "ransomwatch": _ransomware_months,
        "mitre-attack": _campaigns,
        "osv-malicious": lambda rows: rules._packages(rows, now, days=None, prefix=PREFIX),
    }


WINDOWS = {"cisa-kev": rules.KEV_DAYS, "hibp": rules.BREACH_DAYS, "nvd": rules.NVD_DAYS,
           "osv-malicious": rules.PACKAGE_DAYS}
"""The past begins where each live window ends, so no incident is listed twice."""


@lru_cache(maxsize=1)
def _index() -> tuple[dict, ...]:
    """A small entry per past incident — id, severity, date, searchable text, its record — built in
    chunks and kept instead of the incidents themselves. Twenty thousand built incidents held in
    memory came to about 200 MB, too much beside the models in a 512 MB function; a page builds
    only the incidents it shows."""
    records = _data().get("records") or []
    now = datetime.now(UTC)
    builders = _builders(records)
    entries = []
    for source, build in builders.items():
        window = WINDOWS.get(source)
        rows = [r for r in records if r["source"] == source
                and (window is None or (rules._when(r) or now) < now - timedelta(days=window))]
        for start in range(0, len(rows), 500):
            for incident in build(rows[start : start + 500]):
                entries.append({
                    "id": incident.id,
                    "severity": str(incident.severity),
                    "opened_at": incident.opened_at.isoformat(),
                    # The techniques too, so campaigns that worked the same way resemble each other.
                    "text": " ".join(
                        [incident.id, *(h.statement for h in incident.hypotheses),
                         *(link.attack_technique.id for link in incident.causal_chain if link.attack_technique)]
                    ).lower(),
                    "record": incident.event_ids[0],
                    "source": source,
                })
    entries.sort(key=lambda e: e["opened_at"], reverse=True)
    return tuple(entries)


def _build(entry: dict) -> Incident | None:
    record = _by_id().get(entry["record"])
    if record is None:
        return None
    built = _builders(records())[entry["source"]]([record])
    return next((i for i in built if i.id == entry["id"]), None)


def incidents() -> tuple[Incident, ...]:
    """Every past incident, built. For tests and small records; the API pages through `page`."""
    return tuple(i for e in _index() if (i := _build(e)) is not None)


def count() -> int:
    return len(_index())


def get(incident_id: str) -> Incident | None:
    entry = next((e for e in _index() if e["id"] == incident_id), None)
    return _build(entry) if entry else None


def page(
    limit: int = 50, offset: int = 0, kind: str | None = None, q: str | None = None,
    severity: str | None = None,
) -> dict[str, object]:
    """A page of past incidents, newest first, optionally of one kind (`kev`, `nvd`, `breach`, `rw`,
    `campaign`), one severity, or matching every word given."""
    found = list(_index())
    if kind:
        found = [e for e in found if e["id"].startswith(f"{PREFIX}{kind.upper()}-")]
    if severity:
        found = [e for e in found if e["severity"] == severity]
    if q:
        words = q.lower().split()
        found = [e for e in found if all(w in e["text"] for w in words)]
    limit = max(1, min(limit, 200))
    items = [i for e in found[offset : offset + limit] if (i := _build(e)) is not None]
    return {
        "total": len(found),
        "offset": offset,
        "limit": limit,
        "generated": _data().get("generated"),
        "items": [i.model_dump(mode="json") for i in items],
    }


_TOKEN = re.compile(r"[a-z0-9][a-z0-9_.-]*[a-z0-9]")
_STOP = frozenset(
    "the and for with from that this was were has have its are not but can into via all any one "
    "past live kev nvd rw breach campaign pkg cve version versions before after allows allow "
    "attacker attackers remote unauthenticated authenticated vulnerability vulnerable could would "
    "exploited exploit exploitation wild added catalogue cisa known federal remediation due "
    "disclosed cvss critical high medium reported yet group claimed victims leak site claims "
    "unverified own published malicious code package accounts exposed infrastructure active new "
    "indicators last hours days months attributed documented intrusion conducted cyber operation "
    "operations used they their them also which other including malware distributed compromise "
    "threat actor actors activity targeted targeting hints".split()
)


def _tokens(text: str) -> frozenset[str]:
    # Nothing starting with a digit: dates and version numbers are shared by unrelated incidents
    # (every group's claims in the same month), and they outweighed the name that mattered.
    return frozenset(t for t in _TOKEN.findall(text.lower()) if len(t) > 2 and t not in _STOP
                     and not t[0].isdigit())


@lru_cache(maxsize=1)
def _postings() -> tuple[dict[str, list[int]], tuple[frozenset[str], ...]]:
    """Which past incidents each word appears in, so a query reads only the incidents that share
    a word with it instead of all of them."""
    sets = tuple(_tokens(entry["text"]) for entry in _index())
    postings: dict[str, list[int]] = {}
    for position, words in enumerate(sets):
        for word in words:
            postings.setdefault(word, []).append(position)
    return postings, sets


def similar(incident: Incident, limit: int = 6) -> list[dict[str, object]]:
    """Past incidents that resemble `incident`, most alike first, each with the words they share.

    Resemblance is the summed rarity (inverse document frequency) of the words two incidents share:
    a ransomware group's name or a product appears in a handful of the record's incidents and
    weighs a great deal; a word in thousands weighs almost nothing. Plain and checkable, which a
    learned similarity would not be, and every match says which words it rests on."""
    import math

    postings, sets = _postings()
    total = max(len(sets), 1)
    statements = " ".join(h.statement for h in incident.hypotheses)
    techniques = " ".join(l.attack_technique.id for l in incident.causal_chain if l.attack_technique)
    names = _tokens(" ".join(e.name for e in incident.affected_entities))
    query = _tokens(f"{statements} {techniques}") | names
    kind = incident.id.split("-")[1] if "-" in incident.id else ""
    scores: dict[int, float] = {}
    shared: dict[int, list[tuple[float, str]]] = {}
    for word in query:
        found = postings.get(word)
        if not found or len(found) > total // 100:
            continue  # absent, or in more than 1% of the record: it says nothing about this one
        # A word naming who or what was hit (the group, the product) counts double.
        weight = math.log(total / len(found)) * (2.0 if word in names else 1.0)
        for position in found:
            scores[position] = scores.get(position, 0.0) + weight
            shared.setdefault(position, []).append((weight, word))
    index = _index()
    for position in scores:  # the same kind of incident first, when the evidence is close
        if index[position]["id"].split("-")[1] == kind:
            scores[position] *= 1.5
    ranked = sorted(
        (p for p in scores if index[p]["id"] != incident.id),
        key=lambda p: (scores[p], index[p]["opened_at"]),
        reverse=True,
    )
    out = []
    for position in ranked[:limit]:
        built = _build(index[position])
        if built is None:
            continue
        words = [w for _, w in sorted(shared[position], reverse=True)[:4]]
        out.append({"incident": built.model_dump(mode="json"), "shared": words,
                    "score": round(scores[position], 2)})
    return out
