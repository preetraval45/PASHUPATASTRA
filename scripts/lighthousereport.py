"""Summarise Lighthouse JSON reports into one Markdown table (the `lighthouse` workflow).

    python scripts/lighthousereport.py reports/ > docs/research/lighthouse.md

Scores and the metrics behind them, per page and form factor, then the largest opportunities. The
numbers are lab measurements from one GitHub runner with Lighthouse's own throttling (a mid-range
phone on a slow 4G link for mobile), so they compare pages and runs with each other; they are not
what every visitor sees.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

CATEGORIES = ("performance", "accessibility", "best-practices", "seo")
METRICS = (
    ("first-contentful-paint", "FCP"),
    ("largest-contentful-paint", "LCP"),
    ("total-blocking-time", "TBT"),
    ("cumulative-layout-shift", "CLS"),
    ("speed-index", "Speed Index"),
)


def main() -> int:
    reports = sorted(Path(sys.argv[1]).glob("*.json"))
    rows, opportunities = [], []
    for path in reports:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "categories" not in data:
            continue
        page = data["finalDisplayedUrl"].split("vercel.app", 1)[-1] or "/"
        form = data["configSettings"]["formFactor"]
        scores = [round((data["categories"][c]["score"] or 0) * 100) for c in CATEGORIES]
        metrics = [data["audits"][m]["displayValue"] for m, _ in METRICS]
        weight = data["audits"]["total-byte-weight"]["numericValue"] / 1024
        rows.append(f"| `{page}` | {form} | " + " | ".join(map(str, scores)) + " | " + " | ".join(metrics)
                    + f" | {weight:,.0f} KB |")
        for audit in data["audits"].values():
            saving = (audit.get("metricSavings") or {}).get("LCP") or 0
            if audit.get("score") is not None and audit["score"] < 0.9 and saving >= 300:
                opportunities.append((saving, page, form, audit["title"]))
    out = [
        "# Lighthouse (generated)",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by the `lighthouse` workflow from {len(rows)} reports "
        "against the production site. Lab data from one GitHub runner with Lighthouse's throttling; compare "
        "runs and pages with each other. Do not edit by hand.",
        "",
        "| Page | Form | Perf | A11y | Best practices | SEO | " + " | ".join(n for _, n in METRICS) + " | Weight |",
        "|---|---|---|---|---|---|" + "---|" * len(METRICS) + "---|",
        *rows,
        "",
        "## Largest opportunities (estimated LCP saving ≥ 300 ms)",
        "",
    ]
    seen = set()
    for saving, page, form, title in sorted(opportunities, reverse=True):
        if (title, form) in seen:
            continue
        seen.add((title, form))
        out.append(f"- {title} — up to {saving / 1000:.1f} s on `{page}` ({form})")
    if not opportunities:
        out.append("- none above the threshold")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
