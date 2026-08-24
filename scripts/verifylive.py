"""R61: the page says it is live, and the claim is true.

Three clauses, and the middle one is the whole task.

**The age comes from the record, not from the page load.** The check that means
anything is a *comparison between two loads*: reload after waiting, and the
printed age must have grown by roughly the wait. A page deriving freshness from
its own render would print the same "just now" both times — and would keep
printing it while the feed was broken. Asserting on a single load cannot tell
the two apart, which is why this one waits.

**A stale feed reads as stale.** This page is server-rendered, so the call to
`/intel/status` happens on Vercel and a browser cannot intercept it — the first
attempt did exactly that and reported a pass that measured nothing on the way to
reporting a failure that meant nothing.

Split in two instead, each half checked where it can actually be checked. The
*computation* is covered by `testfeeds.py`, which asserts a feed past the
threshold is stale, a never-polled feed is **not** stale, and a quiet feed is not
reported as broken. The *rendering* was proven once by building the site against
a local stub that reports every feed stale, which printed
`last answered … over 3h ago`; what remains here is the contract the render
depends on — that the deployed API still sends the fields the stale branch
reads. A field silently dropped is what would break it.

**The entry renders first and is highlighted after.** Proven by reading the
server HTML — the highlight class must be absent from it entirely — and then
confirming the class appears in the DOM once a watermark exists.
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
PAGE = f"{SITE}/observatory"
WAIT = 70
"""Seconds between the two loads. Long enough that a minute-granularity age has
to tick over; anything shorter and "1m" to "1m" would pass a broken page."""


def age_on_page(text: str) -> int | None:
    match = re.search(r"last synced\s+(?:(\d+)m|(\d+)s|just now)", text)
    if not match:
        return None
    if match.group(1):
        return int(match.group(1)) * 60
    if match.group(2):
        return int(match.group(2))
    return 0


def main() -> int:
    failures: list[str] = []

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # --- the highlight is not in the server HTML -------------------------
        raw = urllib.request.urlopen(
            urllib.request.Request(PAGE, headers={"User-Agent": "Mozilla/5.0 (verify)"}),
            timeout=45,
        ).read().decode("utf-8", "replace")
        if "just-landed" in raw.replace("@keyframes just-landed", "").replace(
            ".just-landed", ""
        ):
            failures.append("the highlight class is in the server HTML — it should be added after paint")
        else:
            print("highlight: absent from the server HTML, as required")
        if "data-entry-at" not in raw:
            failures.append("rows carry no data-entry-at for the highlight to match on")

        # --- the age is from the record, not the render ----------------------
        page.goto(PAGE, wait_until="networkidle")
        first_text = page.locator("main").inner_text()
        first = age_on_page(first_text)
        if first is None:
            failures.append("no 'last synced' on the page at all")
        else:
            print(f"load 1: last synced {first}s ago — waiting {WAIT}s")
            time.sleep(WAIT)
            page.goto(PAGE, wait_until="networkidle")
            second = age_on_page(page.locator("main").inner_text())
            if second is None:
                failures.append("'last synced' vanished on the second load")
            elif second <= first:
                failures.append(
                    f"the age did not grow across {WAIT}s ({first}s then {second}s) — "
                    "it is being derived from page load, not from the record"
                )
            else:
                print(f"load 2: last synced {second}s ago — grew by {second - first}s")

        # --- the stale branch's contract still holds -------------------------
        #
        # Not intercepted in the browser: this page renders on the server, so
        # the request never passes through here. What is checkable from outside
        # is that the API still sends the fields the stale branch reads, since a
        # dropped field would make every feed silently render as healthy.
        status = json.loads(
            urllib.request.urlopen(
                urllib.request.Request(API + "/intel/status", headers={"User-Agent": "verify"}),
                timeout=45,
            ).read()
        )
        required = {"cursor", "synced_at", "age_seconds", "ok", "error", "stale"}
        for name, feed in status["feeds"].items():
            missing = required - set(feed)
            if missing:
                failures.append(f"{name}: /intel/status dropped {sorted(missing)}")
        if "stale_after_hours" not in status:
            failures.append("/intel/status no longer sends stale_after_hours")
        if not failures:
            print(
                f"status contract: {len(status['feeds'])} feeds, all carrying "
                f"{len(required)} freshness fields"
            )

        # --- the highlight does appear once there is a watermark --------------
        marked = page.evaluate(
            """() => {
                 const rows = document.querySelectorAll('[data-entry-at]');
                 if (!rows.length) return -1;
                 const stamps = [...rows].map(r => r.dataset.entryAt).sort();
                 // Pretend we last looked before the oldest entry on the page.
                 sessionStorage.setItem('pashupatastra:observatory:seen', '2000-01-01');
                 return rows.length;
               }"""
        )
        if marked <= 0:
            failures.append("no rows with data-entry-at to highlight")
        else:
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(600)
            highlighted = page.locator(".just-landed").count()
            if highlighted == 0:
                failures.append(
                    "with a watermark set, nothing was highlighted — the effect never runs"
                )
            else:
                print(f"highlight: {highlighted} of {marked} rows marked after paint")

        browser.close()

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
