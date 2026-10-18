"""Snapshot the world's threat landscape from public sources, for the World page.

    python scripts/worldsnapshot.py --out apps/web/lib/world.generated.json

Run daily by `.github/workflows/world-data.yml` on GitHub's runners, never on
anyone's machine. Every source is public and needs no key. Each one is fetched
independently: a source that fails is recorded with the reason, and the page
says so rather than drawing an empty chart.

What is deliberately *not* kept: the names of ransomware victims. They are
published by the criminals as leverage, and repeating them adds nothing to an
aggregate view — the page shows counts by group, country and sector instead.
Indicators are not kept either; only their counts by family and country.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

UA = "Pashupatastra-world-snapshot/1.0 (+https://pashupatastra.vercel.app)"

KEV = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
RANSOMWARE = "https://api.ransomware.live/v2/recentvictims"
FEODO = "https://feodotracker.abuse.ch/downloads/ipblocklist.json"
HIBP = "https://haveibeenpwned.com/api/v3/breaches"


def fetch(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def top(counter: Counter, n: int = 10) -> list[dict[str, object]]:
    return [{"label": str(k), "value": v} for k, v in counter.most_common(n) if k]


def kev(now: datetime) -> dict:
    data = fetch(KEV)
    items = data.get("vulnerabilities", [])
    months: Counter = Counter()
    year_ago = (now - timedelta(days=365)).date().isoformat()
    for v in items:
        added = v.get("dateAdded", "")
        if added >= year_ago:
            months[added[:7]] += 1
    ransomware = sum(1 for v in items if str(v.get("knownRansomwareCampaignUse", "")).lower() == "known")
    latest = sorted(items, key=lambda v: v.get("dateAdded", ""), reverse=True)[:12]
    return {
        "source": KEV,
        "catalog_version": data.get("catalogVersion"),
        "total": len(items),
        "added_last_30_days": sum(
            1 for v in items if v.get("dateAdded", "") >= (now - timedelta(days=30)).date().isoformat()
        ),
        "known_ransomware_use": ransomware,
        "by_month": [{"label": m, "value": months[m]} for m in sorted(months)],
        "top_vendors": top(Counter(v.get("vendorProject") for v in items)),
        "latest": [
            {
                "cve": v.get("cveID"),
                "vendor": v.get("vendorProject"),
                "product": v.get("product"),
                "name": v.get("vulnerabilityName"),
                "added": v.get("dateAdded"),
                "ransomware": str(v.get("knownRansomwareCampaignUse", "")).lower() == "known",
            }
            for v in latest
        ],
    }


def ransomware() -> dict:
    data = fetch(RANSOMWARE)
    items = data if isinstance(data, list) else data.get("victims", [])
    days: Counter = Counter()
    for v in items:
        day = str(v.get("discovered") or v.get("published") or v.get("attackdate") or "")[:10]
        if day:
            days[day] += 1
    return {
        "source": RANSOMWARE,
        "victims": len(items),
        "by_day": [{"label": d, "value": days[d]} for d in sorted(days)][-30:],
        "by_group": top(Counter(v.get("group") or v.get("group_name") for v in items)),
        "by_country": top(Counter(v.get("country") for v in items)),
        "by_sector": top(Counter(v.get("activity") or v.get("sector") for v in items)),
    }


def feodo() -> dict:
    items = fetch(FEODO)
    if not isinstance(items, list):
        items = []
    return {
        "source": FEODO,
        "c2_servers": len(items),
        "online": sum(1 for i in items if str(i.get("status", "")).lower() == "online"),
        "by_malware": top(Counter(i.get("malware") for i in items)),
        "by_country": top(Counter(i.get("country") for i in items)),
    }


def breaches() -> dict:
    items = fetch(HIBP)
    if not isinstance(items, list):
        items = []
    latest = sorted(items, key=lambda b: b.get("AddedDate", ""), reverse=True)[:10]
    classes: Counter = Counter()
    for b in items:
        for c in b.get("DataClasses", []):
            classes[c] += 1
    return {
        "source": HIBP,
        "breaches": len(items),
        "accounts": sum(int(b.get("PwnCount") or 0) for b in items),
        "top_data_classes": top(classes),
        "latest": [
            {
                "title": b.get("Title"),
                "domain": b.get("Domain"),
                "breach_date": b.get("BreachDate"),
                "added": str(b.get("AddedDate", ""))[:10],
                "accounts": int(b.get("PwnCount") or 0),
                "verified": bool(b.get("IsVerified")),
            }
            for b in latest
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("apps/web/lib/world.generated.json"))
    args = parser.parse_args()

    now = datetime.now(UTC)
    snapshot: dict[str, object] = {"as_of": now.isoformat(timespec="seconds")}
    for name, collect in (
        ("kev", lambda: kev(now)),
        ("ransomware", ransomware),
        ("c2", feodo),
        ("breaches", breaches),
    ):
        try:
            snapshot[name] = {"ok": True, **collect()}
            print(f"{name}: ok")
        except Exception as error:  # noqa: BLE001 — one failed source must not sink the rest
            snapshot[name] = {"ok": False, "absent": f"{type(error).__name__}: {str(error)[:160]}"}
            print(f"{name}: FAILED — {error}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
