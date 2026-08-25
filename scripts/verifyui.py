"""Check the deployed site in a real browser at real viewport widths.

Reading the markup is not enough to know what a page renders. Two spans, each
hidden at the other's breakpoint, look duplicated in the HTML and correct on
screen; a contrast ratio cannot be read off a class name at all. This drives a
headless Chromium and asks the page what it actually painted.

Checks, all of them things a person would otherwise have to eyeball:

  wordmark   — the visible header text, per viewport
  overflow   — whether the document scrolls horizontally, which is how a narrow
               layout usually fails first
  console    — page errors, which otherwise surface only as something quietly
               not working

Usage:  python scripts/verifyui.py [url] [--routes /,/incidents,...]
"""

from __future__ import annotations

import argparse

DEFAULT_URL = "https://pashupatastra.vercel.app"

VIEWPORTS = [
    ("mobile", 375, 812),
    ("tablet", 768, 1024),
    # Both sides of the `nav` breakpoint. 1024 is where the header row used to
    # turn on, and where a seventh label was found sitting underneath the search
    # box; 1160 is where it turns on now. A breakpoint checked only from one
    # side is a breakpoint whose whole purpose is untested.
    ("laptop", 1024, 800),
    ("wide-laptop", 1160, 800),
    ("desktop", 1440, 900),
]

# An incident *detail* page is in this list because it was not, and a 46px
# overflow at 375px lived there unnoticed while every route below passed. The
# pages that render the most data are the ones a width sweep most needs.
DEFAULT_ROUTES = ["/", "/how-it-works", "/overview", "/incidents",
                  "/incidents/INC-2026-0903", "/ask", "/observatory",
                  "/blue-team", "/infrastructure", "/actions", "/audit", "/search"]


def check(page, url: str, route: str, label: str, width: int) -> list[str]:
    failures: list[str] = []
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(url + route, wait_until="networkidle")
    # Wait for the webfonts. `display: swap` paints a fallback first, and the
    # fallback is wider — measuring before the real face arrives reports an
    # overflow that exists for a few hundred milliseconds and then does not.
    page.evaluate("() => document.fonts && document.fonts.ready")
    page.wait_for_timeout(120)

    # Every section reachable, at every width.
    #
    # This check exists because its absence let a real regression ship. The nav
    # was an `overflow-x-auto` strip with the scrollbar hidden, so at 768px only
    # "Overview" was on screen — no scrollbar, no fade, nothing to indicate the
    # other four existed. Every element was in the DOM and nothing overflowed
    # its container, so all eighteen layout checks passed while the site could
    # not be navigated.
    #
    # Hence: count what a person can actually see and click, not what exists.
    # The primary sections, which is not the same as every page. Infrastructure
    # and Audit were delisted in R52 — they are still routes, still linked, and
    # deliberately not front doors. `verifyreach.py` is what holds them to being
    # reachable; listing them here would assert the opposite.
    sections = {"Overview", "Incidents", "Ask", "Blue team", "Observatory",
                "Actions"}
    visible = {
        link.inner_text().strip()
        for link in page.locator("header nav[aria-label='Primary'] a").all()
        if link.is_visible()
    }
    if not sections <= visible:
        menu = page.get_by_role("button", name="Open menu")
        if menu.count() and menu.first.is_visible():
            menu.first.click()
            page.wait_for_timeout(250)
            visible |= {
                link.inner_text().strip()
                for link in page.locator("#primary-menu a").all()
                if link.is_visible()
            }
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)
        missing = sections - visible
        if missing:
            failures.append(
                f"{label} {route}: cannot reach {', '.join(sorted(missing))} "
                "— not visible in the header and not in a menu"
            )

    if route == "/":
        # The name lives in the logo artwork now, so it reaches a reader through
        # `alt` rather than as text. Both halves are checked: the accessible name
        # must be right, and the header must not *also* carry the name as text —
        # that pairing is what produced `PASHUPASHUPATASTRA`.
        home = page.locator('header a[href="/"]').first
        artwork = home.locator("img").first
        name = artwork.get_attribute("alt") if artwork.count() else ""
        if "pashupatastra" not in (name or "").lower():
            failures.append(f"{label}: header logo has no accessible name — {name!r}")
        text = home.evaluate("e => e.textContent.trim()")
        if "PASHUPASHU" in (text or "").replace(" ", "").upper():
            failures.append(f"{label}: wordmark duplicated — {text!r}")

    # Compared against the viewport rather than a fixed number: an element wider
    # than the window is the failure, whatever the window happens to be.
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow > 1:
        widest = page.evaluate(
            """() => {
                let worst = {tag: '', width: 0};
                for (const el of document.querySelectorAll('*')) {
                    const r = el.getBoundingClientRect();
                    if (r.right > worst.width) {
                        worst = {tag: el.tagName + '.' + (el.className || '').toString().slice(0, 60),
                                 width: Math.round(r.right)};
                    }
                }
                return worst;
            }"""
        )
        failures.append(
            f"{label} {route}: {overflow}px horizontal overflow at {width}px "
            f"(widest: {widest['tag']} to {widest['width']}px)"
        )

    # Overflow is not the only way to lose a link. Nothing scrolled sideways
    # when a seventh nav label slid underneath the search box at 1024px — the
    # element was the right size, in the right place, and covered. So every
    # header link is hit-tested: if a point belongs to something else, a
    # visitor clicking there does not get this link.
    #
    # Three points across the width, not one. The centre alone accepted a
    # breakpoint where the search field overlapped the last label by 7px, which
    # is a collision that grows the moment a font renders a little wider.
    for hidden in page.evaluate(
        """() => {
             const out = [];
             for (const a of document.querySelectorAll('header a, header button')) {
               const box = a.getBoundingClientRect();
               if (box.width === 0 || box.height === 0) continue;
               const y = box.top + box.height / 2;
               if (y < 0 || y > innerHeight) continue;
               let covered = null;
               for (const x of [box.left + 2, box.left + box.width / 2, box.right - 2]) {
                 if (x < 0 || x > innerWidth) continue;
                 const hit = document.elementFromPoint(x, y);
                 if (hit && (hit === a || a.contains(hit) || hit.contains(a))) continue;
                 covered = hit;
                 break;
               }
               if (covered === null) continue;
               out.push({
                 name: (a.textContent || a.getAttribute('aria-label') || a.tagName).trim().slice(0, 30),
                 over: (covered ? covered.tagName + '.' + (covered.className || '').toString().slice(0, 40) : 'nothing'),
               });
             }
             return out;
           }"""
    ):
        failures.append(
            f"{label} {route}: header item {hidden['name']!r} is covered by "
            f"{hidden['over']} — it is on the page and cannot be clicked"
        )

    for error in errors:
        failures.append(f"{label} {route}: page error — {error}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    parser.add_argument("--routes", default=",".join(DEFAULT_ROUTES))
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    routes = [r for r in args.routes.split(",") if r]
    failures: list[str] = []
    checked = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for label, width, height in VIEWPORTS:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            for route in routes:
                failures += check(page, args.url.rstrip("/"), route, label, width)
                checked += 1
            context.close()
        browser.close()

    print(f"{args.url} — {checked} page/viewport combinations")
    for failure in failures:
        print(f"  FAIL  {failure}")
    if not failures:
        print("  all checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
