"""R66: every shortcut the help sheet lists is a shortcut that works.

The failure mode a keyboard feature has is not "the key does nothing" — that is
noticed in a minute. It is a help sheet that drifts: a key removed from the code
and left in the list, or bound on a page that no longer has anything to move
between. So the sheet is the *input* to this checker. It reads the rows the page
renders and demands that each one be demonstrated, and a row naming a key this
script has no probe for is a failure rather than a skip — adding a shortcut to
the help without teaching this file about it is exactly the drift being guarded
against.

The other three clauses are checked directly:

* **Nothing fires while a text input has focus.** Typed into the header search
  and asserted that the characters landed in the field and the selection did not
  move — not by reading the guard, which is the thing that could be wrong.
* **Every shortcut has a mouse equivalent.** Each row must print one, and the
  two that matter are exercised: the footer button opens the sheet, and clicking
  a card selects it.
* **`Enter` opens the selected one.** Selected the *second* card deliberately.
  A handler that ignored the cursor and opened the first incident would pass a
  check that only ever selected one thing.

Usage:  python scripts/verifykeys.py [--site URL]
"""

from __future__ import annotations

import argparse
import io
import sys

from playwright.sync_api import Page, sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
LIST = "/incidents"

SHEET = '[role="dialog"][aria-label="Keyboard shortcuts"]'
PALETTE = '[role="dialog"][aria-label="Command palette"]'
ANY_DIALOG = '[role="dialog"][aria-modal="true"]'


def selected(page: Page) -> int | None:
    at = page.locator('[data-triage][aria-current="true"]')
    return int(at.get_attribute("data-triage")) if at.count() else None


def close_everything(page: Page) -> None:
    while page.locator(ANY_DIALOG).count():
        page.keyboard.press("Escape")
        page.wait_for_timeout(120)


def open_sheet(page: Page) -> None:
    close_everything(page)
    page.keyboard.press("?")
    page.wait_for_timeout(200)


def read_sheet(page: Page) -> list[dict]:
    """The rows as rendered. `inner_text` per row, because the keys are separate
    `<kbd>` elements and the mouse equivalent is a line under them."""
    return page.locator(SHEET).evaluate(
        """el => [...el.querySelectorAll('li')].map(li => ({
             keys: [...li.querySelectorAll('kbd')].map(k => k.textContent.trim().toLowerCase()),
             does: li.children[0]?.children[1]?.textContent.trim() ?? '',
             mouse: li.children[1]?.textContent.trim() ?? '',
           }))"""
    )


def reset(page: Page) -> None:
    """A fresh page before each probe.

    Selection has no clearing gesture — that is the point of it — so probes that
    ran earlier would otherwise hand the next one a cursor part-way down the
    list, and `k` would be measured from wherever the last probe stopped. The
    first version of this file shared state that way and reported two failures
    that were entirely its own.
    """
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(300)


# -- one probe per shortcut the sheet is allowed to claim ---------------------
#
# Each returns None on success or a sentence on failure, and each starts from a
# freshly loaded page with nothing selected.


def probe_palette(page: Page) -> str | None:
    close_everything(page)
    page.keyboard.press("Control+k")
    page.wait_for_timeout(250)
    if not page.locator(PALETTE).count():
        return "ctrl-k opened no command palette"
    close_everything(page)
    return None


def probe_slash(page: Page) -> str | None:
    close_everything(page)
    page.keyboard.press("/")
    page.wait_for_timeout(200)
    tag = page.evaluate("() => document.activeElement?.tagName?.toLowerCase()")
    if tag != "input":
        return f"/ left focus on <{tag}>, not the search field"
    page.evaluate("() => document.activeElement.blur()")
    return None


def probe_question(page: Page) -> str | None:
    open_sheet(page)
    if not page.locator(SHEET).count():
        return "? opened no shortcut list"
    close_everything(page)
    return None


def probe_escape(page: Page) -> str | None:
    open_sheet(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    if page.locator(SHEET).count():
        return "escape did not close the shortcut list"
    return None


def probe_j(page: Page) -> str | None:
    close_everything(page)
    page.keyboard.press("j")
    page.wait_for_timeout(150)
    if selected(page) != 0:
        return f"j from nothing selected {selected(page)}, expected the first"
    page.keyboard.press("j")
    page.wait_for_timeout(150)
    if selected(page) != 1:
        return f"a second j selected {selected(page)}, expected the second"
    return None


def probe_k(page: Page) -> str | None:
    page.keyboard.press("j")
    page.keyboard.press("j")
    page.wait_for_timeout(150)
    if selected(page) != 1:
        return "could not get down the list to test coming back up"
    page.keyboard.press("k")
    page.wait_for_timeout(150)
    if selected(page) != 0:
        return f"k selected {selected(page)}, expected back to the first"
    return None


def probe_enter(page: Page) -> str | None:
    close_everything(page)
    page.keyboard.press("j")
    page.keyboard.press("j")
    page.wait_for_timeout(150)
    if selected(page) != 1:
        return "could not select the second card to test enter"
    # The href the *selected* card carries, read before navigating.
    want = page.locator('[data-triage="1"] a[href^="/incidents/"]').first.get_attribute("href")
    page.keyboard.press("Enter")
    # Waited on rather than slept through. A fixed pause measures how long the
    # route takes to render, which on a cold dev server is not what is being
    # tested — the first version of this failed for that reason alone.
    try:
        page.wait_for_url(f"**{want}", timeout=20_000)
    except Exception:
        return f"enter went to {page.url}, not the selected {want}"
    page.go_back(wait_until="networkidle")
    page.wait_for_timeout(400)
    return None


PROBES = {
    ("ctrl", "k"): probe_palette,
    ("/",): probe_slash,
    ("?",): probe_question,
    ("esc",): probe_escape,
    ("j",): probe_j,
    ("k",): probe_k,
    ("enter",): probe_enter,
}


def check(page: Page, failures: list[str]) -> None:
    # -- the sheet is findable without knowing the shortcut ------------------
    button = page.get_by_role("button", name="Keyboard shortcuts")
    if not button.count():
        failures.append("no visible way to reach the shortcut list")
    else:
        button.first.click()
        page.wait_for_timeout(250)
        if not page.locator(SHEET).count():
            failures.append("the footer button did not open the shortcut list")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        focused = page.evaluate("() => document.activeElement?.textContent?.trim() ?? ''")
        if "Keyboard shortcuts" not in focused:
            failures.append(
                "closing the sheet dropped focus rather than returning it to the button"
            )

    # -- every listed shortcut works -----------------------------------------
    open_sheet(page)
    rows = read_sheet(page)
    close_everything(page)
    if not rows:
        failures.append("the shortcut list is empty")
    for row in rows:
        keys = tuple(row["keys"])
        if not row["mouse"]:
            failures.append(f"{'+'.join(keys)} lists no mouse equivalent")
        probe = PROBES.get(keys)
        if probe is None:
            failures.append(
                f"the sheet claims {'+'.join(keys)} and this checker cannot demonstrate it"
            )
            continue
        reset(page)
        problem = probe(page)
        if problem:
            failures.append(f"{'+'.join(keys)}: {problem}")

    # every probe this file knows must appear in the sheet, or the list is
    # short — a working shortcut nobody is told about
    listed = {tuple(row["keys"]) for row in rows}
    for keys in PROBES:
        if keys not in listed:
            failures.append(f"{'+'.join(keys)} works but the sheet does not list it")

    # -- nothing fires while a field has focus -------------------------------
    reset(page)
    page.keyboard.press("j")
    page.wait_for_timeout(150)
    before = selected(page)
    field = page.locator('header input[type="search"], header input').first
    field.click()
    field.fill("")
    page.keyboard.type("jjk?")
    page.wait_for_timeout(200)
    if field.input_value() != "jjk?":
        failures.append(f"typing into the header produced {field.input_value()!r}")
    if selected(page) != before:
        failures.append("j moved the selection while a text field had focus")
    if page.locator(ANY_DIALOG).count():
        failures.append("? opened a dialog while a text field had focus")
    page.evaluate("() => document.activeElement.blur()")

    # -- the pointer reaches the same places ---------------------------------
    reset(page)
    cards = page.locator("[data-triage]")
    if cards.count() < 3:
        failures.append(f"only {cards.count()} incidents — too few to test moving between them")
    else:
        cards.nth(2).click(position={"x": 5, "y": 5})
        page.wait_for_timeout(200)
        if selected(page) != 2:
            failures.append(f"clicking the third card selected {selected(page)}")

    # -- and the order on screen is the order j walks -------------------------
    order = page.eval_on_selector_all(
        "[data-triage]", "els => els.map(e => Number(e.dataset.triage))"
    )
    if order != sorted(order):
        failures.append(f"cards are indexed {order} but rendered in that order — j would jump")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=SITE)
    args = parser.parse_args()

    failures: list[str] = []
    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.site.rstrip("/") + LIST, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(500)

        if page.locator(ANY_DIALOG).count():
            failures.append("a modal was open before anything was pressed")

        check(page, failures)
        failures += [f"browser error: {e}" for e in errors]
        browser.close()

    if failures:
        print(f"FAIL ({len(failures)})")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"OK — {len(PROBES)} shortcuts listed, demonstrated, and each with a mouse equivalent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
