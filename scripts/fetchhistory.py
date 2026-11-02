"""Fetch the record of past incidents the API serves beside the live ones (CI deploy step).

Three public sources whose terms allow it, written as records in the same shape the feed poll
stores, so the API builds past incidents with the same rules it builds live ones
(services/api/app/feeds/history.py):

- CISA's Known Exploited Vulnerabilities catalogue, every entry since 2021 (CC0).
- Every breach Have I Been Pwned has published (CC BY 4.0: each incident links its HIBP page,
  which is the attribution the licence asks for). Spam lists and breaches HIBP marks fabricated
  are left out: neither is a breach.
- CVEs NIST's NVD rated critical (three years) or high (one year), a U.S. government work.
- Ransomware leak-site claims from the ransomwatch archive (public domain), counted per group
  per month, never naming a victim.
- MITRE ATT&CK's documented intrusion campaigns, with their techniques (ATT&CK terms of use).

Into a git-ignored file, services/api/app/history/history.json, so it reaches the Lambda archive
and nothing else. A failure here is reported and the API deploys without history.

Usage:  python scripts/fetchhistory.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

UA = "Pashupatastra-history/1.0 (+https://pashupatastra.vercel.app)"
KEV = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
HIBP = "https://haveibeenpwned.com/api/v3/breaches"
NVD = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OUT = Path("services/api/app/history/history.json")


def fetch(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def kev() -> list[dict]:
    rows = []
    for entry in fetch(KEV)["vulnerabilities"]:
        cve = entry.get("cveID")
        added = entry.get("dateAdded")
        if not cve or not added:
            continue
        rows.append({
            "id": f"hist-kev-{cve}",
            "source": "cisa-kev",
            "occurred_at": f"{added}T00:00:00+00:00",
            "entity_key": f"vulnerability:{cve}",
            "labels": {
                "verification": "confirmed",
                "title": str(entry.get("vulnerabilityName", ""))[:200],
                "summary": str(entry.get("shortDescription", ""))[:400],
                "required_action": str(entry.get("requiredAction", ""))[:300],
                "due_date": str(entry.get("dueDate", "")),
                "ransomware": "known" if str(entry.get("knownRansomwareCampaignUse", "")).lower() == "known" else "unknown",
                "vendor": str(entry.get("vendorProject", ""))[:80],
                "product": str(entry.get("product", ""))[:80],
                "cwe": ",".join(entry.get("cwes") or []),
            },
            "provenance": {"source_system": "cisa-kev", "url": f"https://nvd.nist.gov/vuln/detail/{cve}",
                           "offset": added, "license": "CC0-1.0"},
        })
    return rows


def hibp() -> list[dict]:
    rows = []
    for breach in fetch(HIBP):
        if breach.get("IsSpamList") or breach.get("IsFabricated"):
            continue
        name = str(breach.get("Name", ""))
        added = str(breach.get("AddedDate", ""))
        if not name or not added:
            continue
        count = int(breach.get("PwnCount") or 0)
        rows.append({
            "id": f"hist-hibp-{re.sub(r'[^A-Za-z0-9]+', '-', name)}",
            "source": "hibp",
            "occurred_at": added.replace("Z", "+00:00"),
            "entity_key": f"organisation:breach:{name.lower()}",
            "labels": {
                "verification": "corroborated" if breach.get("IsVerified") else "reported",
                "title": f"{breach.get('Title', name)}: {count:,} accounts exposed",
                "accounts": str(count),
                "exposed": ", ".join(breach.get("DataClasses") or [])[:300],
                "breach_date": str(breach.get("BreachDate", "")),
                "domain": str(breach.get("Domain", ""))[:120],
            },
            "provenance": {"source_system": "hibp", "url": f"https://haveibeenpwned.com/PwnedWebsites#{name}",
                           "offset": added, "license": "CC-BY-4.0"},
        })
    return rows


def nvd(severity: str = "CRITICAL", days: int = 365) -> list[dict]:
    """Every CVE NVD published in the last `days` with the given CVSS v3 rating.

    NVD's public API allows five requests in 30 seconds without a key and 120 days per query, so
    the year is read in 120-day windows of up to 2,000 results, six seconds apart."""
    import time
    from datetime import timedelta

    end = datetime.now(UTC)
    rows, start = [], end - timedelta(days=days)
    while start < end:
        stop = min(start + timedelta(days=120), end)
        index = 0
        while True:
            url = (f"{NVD}?cvssV3Severity={severity}&resultsPerPage=2000&startIndex={index}"
                   f"&pubStartDate={start:%Y-%m-%dT%H:%M:%S.000}&pubEndDate={stop:%Y-%m-%dT%H:%M:%S.000}")
            page = fetch(url)
            time.sleep(6)
            for item in page.get("vulnerabilities") or []:
                cve = item.get("cve") or {}
                identifier, published = cve.get("id"), cve.get("published")
                # NVD lists a score per scorer (NVD itself, the CNA); its severity filter matches
                # any of them, so the critical one is the highest.
                metrics = cve.get("metrics") or {}
                scores = [(m.get("cvssData") or {}).get("baseScore")
                          for m in (metrics.get("cvssMetricV31") or []) + (metrics.get("cvssMetricV30") or [])]
                score = max((x for x in scores if x is not None), default=None)
                if not identifier or not published or score is None:
                    continue
                text = next((d.get("value", "") for d in cve.get("descriptions") or [] if d.get("lang") == "en"), "")
                rows.append({
                    "id": f"hist-nvd-{identifier}",
                    "source": "nvd",
                    "occurred_at": published + ("+00:00" if "+" not in published else ""),
                    "entity_key": f"vulnerability:{identifier}",
                    "labels": {"verification": "corroborated", "title": text[:200], "summary": text[:400],
                               "cvss": str(score), "cvss_severity": severity},
                    "provenance": {"source_system": "nvd", "url": f"https://nvd.nist.gov/vuln/detail/{identifier}",
                                   "offset": published, "license": "public domain (NIST)"},
                })
            index += page.get("resultsPerPage") or 0
            if not page.get("resultsPerPage") or index >= page.get("totalResults", 0):
                break
        start = stop
    return rows


RANSOMWATCH = "https://raw.githubusercontent.com/joshhighet/ransomwatch/main/posts.json"
ATTACK = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"


def ransomwatch(minimum: int = 3) -> list[dict]:
    """Ransomware leak-site claims from the ransomwatch archive (public domain, 2020 to mid-2025),
    one record per group per month with at least `minimum` claims. Counts only: no victim name
    leaves this function, because repeating them is publishing the extortion."""
    from collections import Counter

    months: Counter[tuple[str, str]] = Counter()
    for post in fetch(RANSOMWATCH):
        group, when = str(post.get("group_name") or ""), str(post.get("discovered") or "")
        if group and len(when) >= 7:
            months[(group, when[:7])] += 1
    rows = []
    for (group, month), count in months.items():
        if count < minimum:
            continue
        rows.append({
            "id": f"hist-rw-{re.sub(r'[^a-z0-9]+', '-', group.lower())}-{month}",
            "source": "ransomwatch",
            "occurred_at": f"{month}-01T00:00:00+00:00",
            "entity_key": f"organisation:group:{group}",
            "labels": {"group": group, "month": month, "claims": str(count), "verification": "reported",
                       "claimed_by": "the attacker"},
            "provenance": {"source_system": "ransomwatch", "url": f"https://ransomwatch.telemetry.ltd/#/profiles?id={group}",
                           "offset": month, "license": "public domain (Unlicense)"},
        })
    return rows


def _plain(markdown: str) -> str:
    """ATT&CK descriptions carry markdown links and citations; keep the words."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)
    return re.sub(r"\(Citation:[^)]+\)", "", text).strip()


def attack_campaigns() -> list[dict]:
    """MITRE ATT&CK's documented intrusion campaigns, with the techniques each used and the group
    it is attributed to. © The MITRE Corporation; reproduced and distributed with its permission
    under the ATT&CK terms of use."""
    objects = fetch(ATTACK)["objects"]
    live = {o["id"]: o for o in objects if not o.get("revoked") and not o.get("x_mitre_deprecated")}
    techniques: dict[str, list[str]] = {}
    groups: dict[str, str] = {}
    for rel in objects:
        if rel.get("type") != "relationship" or rel.get("revoked"):
            continue
        source, target = live.get(rel.get("source_ref")), live.get(rel.get("target_ref"))
        if not source or not target or source.get("type") != "campaign":
            continue
        if rel.get("relationship_type") == "uses" and target.get("type") == "attack-pattern":
            ext = next((r for r in target.get("external_references", []) if r.get("source_name") == "mitre-attack"), {})
            phase = next((p["phase_name"] for p in target.get("kill_chain_phases", []) if p.get("kill_chain_name") == "mitre-attack"), "")
            if ext.get("external_id"):
                techniques.setdefault(source["id"], []).append(
                    f"{ext['external_id']}|{target['name']}|{phase.replace('-', ' ').title()}")
        elif rel.get("relationship_type") == "attributed-to" and target.get("type") == "intrusion-set":
            groups[source["id"]] = target["name"]
    rows = []
    for campaign in live.values():
        if campaign.get("type") != "campaign":
            continue
        ext = next((r for r in campaign.get("external_references", []) if r.get("source_name") == "mitre-attack"), {})
        cid = ext.get("external_id")
        if not cid:
            continue
        rows.append({
            "id": f"hist-attack-{cid}",
            "source": "mitre-attack",
            "occurred_at": campaign.get("first_seen") or campaign.get("created"),
            "entity_key": f"organisation:campaign:{cid}",
            "labels": {"campaign": cid, "name": campaign["name"], "summary": _plain(campaign.get("description", ""))[:900],
                       "first_seen": str(campaign.get("first_seen", ""))[:10], "last_seen": str(campaign.get("last_seen", ""))[:10],
                       "group": groups.get(campaign["id"], ""), "techniques": ";".join(sorted(set(techniques.get(campaign["id"], [])))),
                       "verification": "corroborated"},
            "provenance": {"source_system": "mitre-attack", "url": ext.get("url") or f"https://attack.mitre.org/campaigns/{cid}/",
                           "offset": campaign.get("modified"), "license": "MITRE ATT&CK terms of use"},
        })
    return rows


def main() -> int:
    records = kev() + hibp()
    # Each source on its own: one that fails costs its records, never the others'.
    for name, fetcher in (
        ("nvd critical, 3 years", lambda: nvd("CRITICAL", 365 * 3)),
        ("nvd high, 1 year", lambda: nvd("HIGH", 365)),
        ("ransomwatch", ransomwatch),
        ("mitre attack campaigns", attack_campaigns),
    ):
        try:
            records += fetcher()
        except Exception as exc:  # noqa: BLE001
            print(f"{name} skipped: {type(exc).__name__}: {exc}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": datetime.now(UTC).isoformat(timespec="seconds"),
                               "records": records}, separators=(",", ":")), encoding="utf-8")
    counts = {s: sum(1 for r in records if r["source"] == s) for s in ("cisa-kev", "hibp", "nvd", "ransomwatch", "mitre-attack")}
    print(f"history: {counts}, {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
