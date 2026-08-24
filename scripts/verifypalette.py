"""R60's done-when, clause by clause, in a real browser.

Every claim here is about behaviour under a keyboard, so every check presses
keys. Asserting that a component renders the string "esc" would prove that
somebody wrote a hint, not that Escape closes anything.

The focus checks are the ones worth having. `document.activeElement` is read
before opening and again after closing, and the two must be the same element —
a dialog that drops focus on `<body>` leaves a keyboard user's next Tab
starting from the top of the document, which is how a shortcut meant to save
time costs it.
"""

from __future__ import annotations

import io
import sys

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
PAGES = ["/", "/overview", "/incidents", "/observatory", "/ask", "/actions", "/how-it-works"]

DIALOG = "[role='dialog'][aria-label='Command palette']"


def main() -> int:
    failures: list[str] = []

    with sync_playwright() as play:
        browser = play.chromium.launch()

        # --- opens from any page ---------------------------------------------
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        for path in PAGES:
            page.goto(SITE + path, wait_until="networkidle")
            page.keyboard.press("Control+k")
            page.wait_for_timeout(150)
            if page.locator(DIALOG).count() == 0:
                failures.append(f"{path}: Ctrl-K did not open the palette")
            else:
                page.keyboard.press("Escape")
                page.wait_for_timeout(100)
                if page.locator(DIALOG).count() != 0:
                    failures.append(f"{path}: Escape did not close it")
        print(f"opens and closes on {len(PAGES) - len(failures)}/{len(PAGES)} pages")

        # --- focus is captured and returned -----------------------------------
        page.goto(SITE + "/overview", wait_until="networkidle")
        page.keyboard.press("Tab")  # put focus on something real first
        before = page.evaluate("() => document.activeElement?.outerHTML?.slice(0, 60)")
        page.keyboard.press("Control+k")
        page.wait_for_timeout(150)
        focused = page.evaluate("() => document.activeElement?.id")
        if focused != "palette-input":
            failures.append(f"focus did not move into the palette (it is on {focused!r})")
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        after = page.evaluate("() => document.activeElement?.outerHTML?.slice(0, 60)")
        if before != after:
            failures.append("focus was not returned to the element that had it")
        else:
            print("focus: captured on open, returned on close")

        # --- the trap ---------------------------------------------------------
        page.keyboard.press("Control+k")
        page.wait_for_timeout(150)
        for _ in range(6):
            page.keyboard.press("Tab")
        trapped = page.evaluate("() => document.activeElement?.id")
        if trapped != "palette-input":
            failures.append(f"Tab escaped the dialog (focus on {trapped!r})")
        else:
            print("focus trap: six Tabs stayed inside the dialog")

        # --- arrows move the selection ----------------------------------------
        first = page.locator("[role='option'][aria-selected='true']").inner_text()
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(80)
        second = page.locator("[role='option'][aria-selected='true']").inner_text()
        if first == second:
            failures.append("ArrowDown did not move the selection")
        page.keyboard.press("ArrowUp")
        page.wait_for_timeout(80)
        back = page.locator("[role='option'][aria-selected='true']").inner_text()
        if back != first:
            failures.append("ArrowUp did not move the selection back")
        if first != second and back == first:
            print("arrows: down moves, up returns")

        # --- typing filters, and Enter navigates ------------------------------
        page.keyboard.type("observ")
        page.wait_for_timeout(200)
        shown = page.locator("[role='option']").count()
        page.keyboard.press("Enter")
        page.wait_for_url("**/observatory**", timeout=8000)
        print(f"typing filtered to {shown} rows and Enter navigated to /observatory")
        if page.locator(DIALOG).count() != 0:
            failures.append("the palette stayed open after navigating")

        # --- it does not round-trip on keystroke ------------------------------
        page.goto(SITE + "/overview", wait_until="networkidle")
        calls: list[str] = []
        page.on("request", lambda request: calls.append(request.url))
        page.keyboard.press("Control+k")
        page.wait_for_timeout(200)
        calls.clear()
        page.keyboard.type("incident")
        page.wait_for_timeout(500)
        api_calls = [url for url in calls if "/api/" in url or "execute-api" in url]
        if api_calls:
            failures.append(f"typing fired {len(api_calls)} API request(s): {api_calls[:2]}")
        else:
            print("no API request fired while typing — the index is already in memory")
        page.keyboard.press("Escape")

        # --- touch keeps a visible affordance ---------------------------------
        touch = browser.new_page(
            viewport={"width": 390, "height": 844},
            has_touch=True,
            is_mobile=True,
        )
        touch.goto(SITE + "/overview", wait_until="networkidle")
        affordance = touch.locator("header a[aria-label*='Search'], header input[type='search']")
        if affordance.count() == 0 or not affordance.first.is_visible():
            failures.append("no visible search affordance at 390px — only a shortcut")
        else:
            print("touch: a visible search affordance, not just a shortcut")

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
