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
    ("desktop", 1440, 900),
]

DEFAULT_ROUTES = ["/", "/incidents", "/infrastructure", "/actions", "/audit", "/search"]


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
