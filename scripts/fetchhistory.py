"""Fetch the record of past incidents the API serves beside the live ones (CI deploy step).

Three public sources whose terms allow it, written as records in the same shape the feed poll
stores, so the API builds past incidents with the same rules it builds live ones
(services/api/app/feeds/history.py):

- CISA's Known Exploited Vulnerabilities catalogue, every entry since 2021 (CC0).
- Every breach Have I Been Pwned has published (CC BY 4.0: each incident links its HIBP page,
  which is the attribution the licence asks for). Spam lists and breaches HIBP marks fabricated
  are left out: neither is a breach.
- A year of CVEs NIST's NVD rated critical (CVSS v3), a U.S. government work.

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


def nvd_critical(days: int = 365) -> list[dict]:
    """Every CVE NVD published in the last `days` with a critical CVSS v3 rating.

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
            url = (f"{NVD}?cvssV3Severity=CRITICAL&resultsPerPage=2000&startIndex={index}"
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
                               "cvss": str(score), "cvss_severity": "CRITICAL"},
                    "provenance": {"source_system": "nvd", "url": f"https://nvd.nist.gov/vuln/detail/{identifier}",
                                   "offset": published, "license": "public domain (NIST)"},
                })
            index += page.get("resultsPerPage") or 0
            if not page.get("resultsPerPage") or index >= page.get("totalResults", 0):
                break
        start = stop
    return rows


def main() -> int:
    records = kev() + hibp()
    try:
        records += nvd_critical()
    except Exception as exc:  # noqa: BLE001 - NVD is the slowest source; the others still ship
        print(f"nvd skipped: {type(exc).__name__}: {exc}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": datetime.now(UTC).isoformat(timespec="seconds"),
                               "records": records}, separators=(",", ":")), encoding="utf-8")
    counts = {s: sum(1 for r in records if r["source"] == s) for s in ("cisa-kev", "hibp", "nvd")}
    print(f"history: {counts}, {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
