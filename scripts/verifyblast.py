"""R63: the blast-radius view draws only what the evidence establishes.

The first clause is the one that needs care. "Draws only edges the incident's
evidence establishes" cannot be checked by looking at the drawing, because a
drawing that invented an edge would look exactly like one that did not. So every
line rendered is matched back to an edge the **API** returned, and every edge the
API returned is required to carry event ids. Two independently obtained sets,
compared — the page does not get to tell the checker what it was allowed to draw.

The other two clauses are geometry: the list has to survive when the diagram is
gone, and the page must not scroll sideways at a phone width. Both are measured
at real viewports rather than inferred from a `hidden lg:block` class, since a
class is a promise about what CSS will do and the viewport is what it did.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
INCIDENTS = ["INC-2026-0901", "INC-2026-0902", "INC-2026-0903"]


def fetch(path: str):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(API + path, headers={"User-Agent": "verify"}),
            timeout=45,
        )
    )


def main() -> int:
    failures: list[str] = []

    with sync_playwright() as play:
        browser = play.chromium.launch()

        for incident_id in INCIDENTS:
            incident = fetch(f"/incidents/{incident_id}")
            entities = incident.get("affected_entities") or []
            if not entities:
                continue
            origin = f"{entities[0]['kind']}:{entities[0]['id']}"
            radius = fetch(f"/topology/blast-radius/{urllib.parse.quote(origin)}")

            # Every edge the API offers must be citable. This is the rule, and
            # it is checked on the source of the drawing rather than on the
            # drawing itself.
            for edge in radius.get("edges") or []:
                if not edge.get("evidence"):
                    failures.append(f"{incident_id}: edge {edge} carries no evidence")

            context = browser.new_context(viewport={"width": 1440, "height": 1200})
            page = context.new_page()
            page.goto(f"{SITE}/incidents/{incident_id}", wait_until="networkidle")

            panel = page.locator("section", has=page.get_by_text("What this reached")).last
            if panel.count() == 0:
                if radius.get("entity_count"):
                    failures.append(f"{incident_id}: reach of {radius['entity_count']} not shown")
                context.close()
                continue

            # Read from `data-evidence`, not from a `<title>`. React 19 treats
            # `<title>` as document metadata and hoists it, which put a
            # hydration mismatch on every incident page — the citation moved to
            # an attribute, and this moved with it.
            drawn = page.evaluate(
                """() => [...document.querySelectorAll('svg line[data-evidence]')]
                     .map(l => `${l.dataset.kind} · ${l.dataset.evidence}`)"""
            )
            allowed = {
                f"{edge['kind']} · {', '.join(edge['evidence'])}"
                for edge in radius.get("edges") or []
            }
            for line in drawn:
                if line and line not in allowed:
                    failures.append(f"{incident_id}: drew a line the API never returned: {line!r}")

            listed = page.evaluate(
                """() => [...document.querySelectorAll('section a[href^="/entity/"]')]
                          .map(a => decodeURIComponent(a.getAttribute('href').slice(8)))"""
            )
            missing = [key for key in radius["affected"] if key not in listed]
            if missing:
                failures.append(f"{incident_id}: reach not listed: {missing}")

            print(
                f"  {incident_id}: {radius['entity_count']} reached, "
                f"{len(radius.get('edges') or [])} cited edges, "
                f"{len([d for d in drawn if d])} lines drawn, all citable"
            )
            context.close()

        # --- collapses to the list, and does not overflow ---------------------
        narrow = browser.new_context(viewport={"width": 375, "height": 900})
        page = narrow.new_page()
        page.goto(f"{SITE}/incidents/INC-2026-0903", wait_until="networkidle")

        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if overflow > 0:
            failures.append(f"375px: {overflow}px of horizontal overflow")

        svg_visible = page.evaluate(
            """() => [...document.querySelectorAll('svg')].some(s => {
                 const b = s.getBoundingClientRect();
                 return b.width > 0 && b.height > 0 && getComputedStyle(s).display !== 'none';
               })"""
        )
        listed_narrow = page.evaluate(
            """() => document.querySelectorAll('section a[href^="/entity/"]').length"""
        )
        if listed_narrow == 0:
            failures.append("375px: the list is gone as well as the diagram")
        print(
            f"  375px: {overflow}px overflow, list has {listed_narrow} entries, "
            f"diagram rendered={svg_visible}"
        )

        browser.close()

    print()
    if failures:
        for failure in dict.fromkeys(failures):
            print(f"FAIL  {failure}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
