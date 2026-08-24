"""R58's done-when, checked at the viewports a visitor actually uses.

"A visitor who reads nothing but the first screen reaches a real incident in one
click" is a claim about geometry, so it is measured as geometry: the link's
bounding box must lie entirely within the viewport before any scrolling.

Keyboard reach is checked by tabbing, not by looking for a `focusable` class —
a class is a promise and Tab is the thing a keyboard user actually does.
"""

from __future__ import annotations

import io
import sys

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app/"
VIEWPORTS = [
    ("desktop", 1440, 900),
    ("laptop", 1366, 768),
    ("small laptop", 1280, 720),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
    ("small mobile", 360, 640),
]


def main() -> int:
    failures: list[str] = []

    with sync_playwright() as play:
        browser = play.chromium.launch()

        for theme in ("dark", "light"):
            for name, width, height in VIEWPORTS:
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    color_scheme=theme,
                )
                page.goto(SITE, wait_until="networkidle")

                label = page.locator("p", has_text="Start here").first
                if label.count() == 0:
                    failures.append(f"{theme} {name}: no 'Start here' label")

                above_fold = []
                for link in page.locator("main a").all():
                    box = link.bounding_box()
                    if box and box["y"] + box["height"] <= height and box["y"] >= 0:
                        above_fold.append(
                            (link.inner_text().strip(), link.get_attribute("href") or "")
                        )

                incident = [a for a in above_fold if a[1].startswith("/incidents/")]
                observatory = [a for a in above_fold if a[1] == "/observatory"]
                if not incident:
                    failures.append(f"{theme} {name}: no incident link on the first screen")
                if not observatory:
                    failures.append(f"{theme} {name}: no real-attack link on the first screen")

                if theme == "dark" and name == "desktop":
                    # Keyboard: Tab until the primary lands, rather than trusting
                    # that a class named `focusable` focuses anything.
                    page.keyboard.press("Tab")
                    reached = False
                    for _ in range(24):
                        href = page.evaluate(
                            "() => document.activeElement && document.activeElement.getAttribute('href')"
                        )
                        if href and href.startswith("/incidents/"):
                            reached = True
                            break
                        page.keyboard.press("Tab")
                    if not reached:
                        failures.append("keyboard: never reached the incident link by tabbing")
                    else:
                        print("  keyboard: reached the incident link by tabbing")

                print(
                    f"  {theme:5} {name:13} {width}x{height}  "
                    f"incident={'yes' if incident else 'NO'}  "
                    f"attacks={'yes' if observatory else 'NO'}"
                )
                page.close()

        # The label must not oversell a scripted scenario.
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(SITE, wait_until="networkidle")
        body = page.locator("main").inner_text().lower()
        if "real incident" in body:
            failures.append(
                "the page calls a scripted scenario a 'real incident' — "
                "the honesty rule, broken on the first screen"
            )
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
