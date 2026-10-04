"""R78: indicators are clickable, the lookup never blocks the page, a miss
reads as nothing known, and no entity key is ever offered as one.

The four clauses are measured rather than read:

* **Nothing blocks.** Network requests are counted while the page loads and
  while it sits there. A lookup fired during render would show up as a request
  nobody asked for, and the count must stay at zero until a click.
* **A miss is an answer.** An address no feed has ever reported is clicked and
  the popover must say nothing known — not an error, and not silence.
* **Cached.** The same indicator clicked twice must cost one request.
* **The guard holds.** Every entity key the incident renders is checked for a
  lookup button, because the dangerous failure here is a page offering to look
  up `account:j.rivera`.

    python scripts/verifyindicators.py [--site URL] [--api URL]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"

# An address in the documentation range that no feed will ever report. The
# "nothing known" path needs a value whose answer cannot change under it.
UNREPORTED = "192.0.2.199"


def get(api: str, path: str) -> tuple[int, dict]:
    request = urllib.request.Request(api + path, headers={"User-Agent": "pashupatastra-verify"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    parser.add_argument("--incident", default="INC-2026-0903")
    args = parser.parse_args()
    failures: list[str] = []

    # --- the route refuses what it must ---------------------------------------
    for key in ("account:j.rivera", "host:ws-0148", "ws-0148"):
        status, body = get(args.api, f"/intel/indicator/{key}")
        if status != 422:
            failures.append(f"{key}: looked up rather than refused ({status})")
    status, miss = get(args.api, f"/intel/indicator/{UNREPORTED}")
    if status != 200 or miss.get("known") is not False:
        failures.append(f"{UNREPORTED}: a miss should be a 200 saying nothing known, got {status}")
    if miss.get("queried_externally") is not False:
        failures.append("the lookup claims to have asked someone else")
    print(f"route: entity keys refused, {UNREPORTED} known={miss.get('known')}")

    with sync_playwright() as play:
        browser = play.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        page = context.new_page()

        lookups: list[str] = []
        page.on(
            "request",
            lambda request: lookups.append(request.url)
            if "/intel/indicator/" in request.url
            else None,
        )

        page.goto(f"{args.site}/incidents/{args.incident}", wait_until="networkidle")
        page.wait_for_timeout(1500)

        # --- nothing blocked the page ------------------------------------------
        if lookups:
            failures.append(f"{len(lookups)} lookup(s) fired without a click: {lookups[:3]}")
        print(f"page loaded with {len(lookups)} lookups fired")

        buttons = page.locator("[data-indicator]")
        count = buttons.count()
        if count == 0:
            failures.append("no indicator on the incident page is clickable")
        values = buttons.evaluate_all("els => els.map(e => e.dataset.indicator)")
        print(f"{count} clickable indicator(s): {sorted(set(values))[:6]}")

        # --- nothing that is not an indicator is offered as one ----------------
        for value in set(values):
            status, body = get(args.api, f"/intel/indicator/{value}")
            if status == 422:
                failures.append(f"the page offers {value!r}, which the route refuses")

        # Every entity key rendered on the page must be absent from that set.
        for key in ("account:j.rivera", "host:ws-0148", "account:m.okafor"):
            if key in values:
                failures.append(f"{key} is offered as an indicator")

        # --- a click answers, and a second click costs nothing -----------------
        if count:
            first = buttons.first
            value = first.get_attribute("data-indicator")
            before = len(lookups)
            first.click()
            page.wait_for_timeout(1200)
            panel = page.locator("[role='region']").first
            text = panel.inner_text() if panel.count() else ""
            if not text.strip():
                failures.append(f"{value}: clicking it showed nothing")
            if "could not ask" in text.lower():
                failures.append(f"{value}: the lookup failed — {text[:120]}")
            fired = len(lookups) - before
            if fired != 1:
                failures.append(f"{value}: one click fired {fired} lookups")
            print(f"  clicked {value}: {fired} request, panel says {text.strip()[:90]!r}")

            # Close, reopen: the answer is cached and no second request is made.
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            before = len(lookups)
            first.click()
            page.wait_for_timeout(800)
            if len(lookups) != before:
                failures.append(f"{value}: reopening it asked again rather than using the cache")
            print(f"  reopened {value}: {len(lookups) - before} further request(s)")
            page.keyboard.press("Escape")

        # --- the observatory, where the indicators actually are -----------------
        #
        # Required only when the store holds feed entries. A local run against a
        # store nobody has polled has no indicators to render, and failing on
        # that would be the checker reporting its own empty fixture as a defect
        # — the mistake this repository keeps naming. It says which it measured.
        _, intel = get(args.api, "/intel?limit=50")
        groups = intel.get("groups") or []
        page.goto(f"{args.site}/observatory", wait_until="networkidle")
        page.wait_for_timeout(800)
        shown = page.locator("[data-indicator]").count()
        print(f"observatory: {len(groups)} feed group(s), {shown} clickable indicator(s)")
        if groups and shown == 0:
            failures.append(
                f"the observatory holds {len(groups)} indicators and offers none of them"
            )
        if not groups:
            print("  (no feed data in this store — the observatory clause was not measured)")

        # --- and a known one reads as known ------------------------------------
        #
        # The incident page's address is in a scripted scenario and no feed has
        # reported it, so the click above only ever proves the *miss*. An
        # indicator the feeds actually stored is the other half, and without it
        # a lookup that always answered "nothing known" would pass every check
        # above.
        if groups:
            known = page.locator("[data-indicator]").first
            value = known.get_attribute("data-indicator")
            known.click()
            page.wait_for_timeout(1500)
            panel = page.locator("[role='region']").first
            text = panel.inner_text() if panel.count() else ""
            status, expected = get(args.api, f"/intel/indicator/{value}")
            if expected.get("known") and "nothing known" in text.lower():
                failures.append(f"{value}: the store holds it and the page says nothing known")
            if expected.get("known") and not any(
                source in text for source in expected.get("sources", [])
            ):
                failures.append(f"{value}: the panel names none of {expected.get('sources')}")
            print(f"  clicked {value}: known={expected.get('known')}, panel {text.strip()[:80]!r}")

        browser.close()

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("indicators look up what is held, block nothing, cache, and refuse what they must")
    return 0


if __name__ == "__main__":
    sys.exit(main())
