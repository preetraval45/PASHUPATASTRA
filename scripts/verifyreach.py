"""Can a visitor still get to the pages that are not in the navigation?

R52 removed Infrastructure and Audit as front doors on the grounds that nobody
arrives looking for them. That is only defensible if they remain easy to reach
from the place the question actually occurs, and the task was explicit that this
be **verified by clicking, not by reading the code** — a link that exists in the
source and is covered, disabled, or scrolled off is not a link.

So this drives a real browser: start at the overview, click, and see where it
lands. It also walks the visitor's own path — overview to an incident to the map
— because a route being reachable by some contrived sequence is not the claim.

    python scripts/verifyreach.py https://pashupatastra.vercel.app
"""

from __future__ import annotations

import argparse
import sys

# (label, where the visitor starts, where it must end up, how many clicks)
#
# The start matters. An earlier version began every journey at the overview,
# so "the map, from an incident" was satisfied by the overview's own link to
# the map — the shortest path, and not the one being claimed. A check whose
# label does not describe what it does is the failure mode this whole session
# kept running into.
JOURNEYS = [
    # `/` is the landing page since R53; the console lives at `/overview`, and
    # these journeys are about the console's own links.
    ("a real incident, from the landing page", "/", "/incidents/INC-", 1),
    ("the map, from the overview", "/overview", "/infrastructure", 1),
    ("the audit trail, from the overview", "/overview", "/audit", 1),
    ("an incident, from the overview", "/overview", "/incidents/INC-", 1),
    ("the map, from an incident", "/incidents/INC-2026-0901", "/infrastructure", 1),
    ("the audit trail, from an incident", "/incidents/INC-2026-0901", "/audit", 2),
]


def reachable(page, base: str, start: str, destination: str, budget: int) -> tuple[bool, list[str]]:
    """Breadth-first over real clicks from `start`, within `budget` hops."""
    trail: list[str] = []
    frontier = [(start, [])]
    seen = {start}
    for _ in range(budget):
        nxt = []
        for path, history in frontier:
            page.goto(base + path, wait_until="networkidle")
            page.wait_for_timeout(500)
            # Only links a person can actually see and click.
            for link in page.locator("#main a").all():
                if not link.is_visible():
                    continue
                href = link.get_attribute("href") or ""
                if not href.startswith("/"):
                    continue
                if href.startswith(destination):
                    return True, [*history, f"{path} → {href}"]
                if href not in seen:
                    seen.add(href)
                    nxt.append((href, [*history, f"{path} → {href}"]))
        frontier = nxt
        trail = [h for _, hist in frontier for h in hist]
    return False, trail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", default="https://pashupatastra.vercel.app")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed")
        return 2

    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})

        # The delisted routes must not be in the navigation, or this proves
        # nothing: it would be finding them in the header it was told to check
        # they had left.
        page.goto(args.base, wait_until="networkidle")
        page.wait_for_timeout(600)
        nav = [
            (link.get_attribute("href") or "")
            for link in page.locator("header nav[aria-label='Primary'] a").all()
        ]
        for delisted in ("/infrastructure", "/audit"):
            if delisted in nav:
                failures.append(f"{delisted} is still in the primary navigation")
                print(f"  x {delisted} is still a front door")

        for label, start, destination, budget in JOURNEYS:
            ok, trail = reachable(page, args.base, start, destination, budget)
            print(f"  {'ok' if ok else 'x '} {label} (within {budget} click"
                  f"{'s' if budget > 1 else ''})")
            if ok:
                print(f"      {trail[-1]}")
            else:
                failures.append(f"{label}: never reached {destination}")
                print(f"      never reached {destination}")

        browser.close()

    if failures:
        print(f"\n{len(failures)} problem(s)")
        return 1
    print("\nevery delisted route is still reachable by clicking")
    return 0


if __name__ == "__main__":
    sys.exit(main())
