"""R62: the chain draws itself, and is complete the whole time it is drawing.

The clause that needs real work is *no text is unreadable at any point in the
sequence*. "At any point" is a claim about every frame, so it is sampled as
frames: the page is loaded, and while the animation runs the computed opacity of
every text node in the chain is read repeatedly. A single check after the
animation finishes would pass on a design that fades text in from zero, which is
exactly the design this clause exists to forbid.

The first clause is checked against the **server HTML** rather than the DOM.
Asking the rendered page whether the chain is present proves nothing about
whether JavaScript built it; asking the bytes the server sent does.
"""

from __future__ import annotations

import io
import sys
import urllib.request

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
INCIDENT = "/incidents/INC-2026-0903"
SAMPLES = 26
MIN_OPACITY = 0.95

VIEWPORTS = [
    ("desk", {"width": 1280, "height": 1000}, {}),
    # A phone, as a phone. R67 asks whether the reveal works at this width or is
    # absent by design; it is neither hidden nor previously measured here.
    ("phone", {"width": 390, "height": 844}, {"is_mobile": True, "has_touch": True}),
]


def sample_reveal(browser, url: str, label: str, viewport: dict, failures: list, **extra) -> None:
    """Watch one reveal, frame by frame, at one viewport.

    Taken out of `main` so it can be run at a phone width as well as a desk one.
    R62 was only ever sampled at 1280x1000, which is the width the animation was
    designed at — the reveal is a sequence of delays and transforms, and a
    marker that collapses does so in whatever layout it is given. Checking one
    width and calling the clause satisfied is checking the case that was already
    known to work.
    """
    context = browser.new_context(viewport=viewport, **extra)
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")
    # Wait for layout before measuring it. Sampling from `domcontentloaded`
    # read every box as 0x0 and reported the whole chain hidden — a checker
    # measuring a page that had not been drawn yet, and reporting the
    # absence as a defect. The reveal starts on mount, so this waits for the
    # first marker and is still inside the sequence.
    page.wait_for_selector("[data-chain] [data-node]", state="visible", timeout=20000)

    worst = 1.0
    worst_text = ""
    for _ in range(SAMPLES):
        rows = page.evaluate(
            """() => {
                 const out = [];
                 for (const el of document.querySelectorAll('[data-chain] p, [data-chain] a')) {
                   const style = getComputedStyle(el);
                   let opacity = parseFloat(style.opacity);
                   // Inherited fade: multiply up the ancestor chain.
                   let node = el.parentElement;
                   while (node && node !== document.body) {
                     opacity *= parseFloat(getComputedStyle(node).opacity);
                     node = node.parentElement;
                   }
                   const box = el.getBoundingClientRect();
                   out.push({
                     opacity,
                     hidden: style.visibility === 'hidden' || style.display === 'none',
                     empty: box.width === 0 && box.height === 0,
                     text: (el.textContent || '').slice(0, 40),
                   });
                 }
                 return out;
               }"""
        )
        for row in rows:
            if row["hidden"] or row["empty"]:
                failures.append(f"{label}: chain text hidden mid-sequence: {row['text']!r}")
            if row["opacity"] < worst:
                worst, worst_text = row["opacity"], row["text"]

        # Geometry too, on every frame — a marker that collapses only
        # during its own delay is invisible on exactly the frames a check
        # run afterwards would miss.
        for marker in page.evaluate(
            """() => [...document.querySelectorAll('[data-chain] [data-node]')].map(el => {
                 const b = el.getBoundingClientRect();
                 return { h: b.height, w: b.width, n: (el.textContent || '').trim() };
               })"""
        ):
            if marker["h"] < 4 or marker["w"] < 4:
                failures.append(
                    f"{label}: chain marker {marker['n']!r} collapsed to "
                    f"{marker['w']:.0f}x{marker['h']:.0f} mid-sequence"
                )
        page.wait_for_timeout(60)

    # --- the markers stay visible through every frame ---------------------
    #
    # Added after a screenshot caught what the opacity sampler could not.
    # The reveal used positional CSS selectors, and the final step renders
    # no rail — so on that one row the marker matched `:first-child` and was
    # handed the rail's `scaleY(0)`. It was invisible for the length of its
    # own delay, at full opacity the whole time.
    #
    # Geometry, therefore, not opacity: a transform can hide an element
    # without changing a single colour, and only the rendered box knows.
    markers = page.evaluate(
        """() => [...document.querySelectorAll('[data-chain] [data-node]')].map(el => {
             const box = el.getBoundingClientRect();
             return { h: box.height, w: box.width, n: (el.textContent || '').trim() };
           })"""
    )
    for marker in markers:
        if marker["h"] < 4 or marker["w"] < 4:
            failures.append(
                f"{label}: chain marker {marker['n']!r} collapsed to "
                f"{marker['w']:.0f}x{marker['h']:.0f} during the reveal"
            )

    if worst < MIN_OPACITY:
        failures.append(
            f"{label}: chain text dropped to opacity {worst:.2f} during the reveal "
            f"({worst_text!r}) — unreadable text is what this clause forbids"
        )
    else:
        print(f"{label}: across {SAMPLES} frames the faintest chain text was opacity {worst:.2f}")



def main() -> int:
    failures: list[str] = []
    url = SITE + INCIDENT

    # --- the chain is in the HTML the server sent ---------------------------
    raw = (
        urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verify)"}),
            timeout=45,
        )
        .read()
        .decode("utf-8", "replace")
    )
    steps_in_html = raw.count('id="chain-')
    if steps_in_html < 2:
        failures.append(f"only {steps_in_html} chain steps in the server HTML")
    else:
        print(f"server HTML already contains {steps_in_html} chain steps")
    if "chain-building" in raw:
        failures.append("the animation class is in the server HTML — it must be added after paint")

    with sync_playwright() as play:
        browser = play.chromium.launch()

        # --- text stays readable through every frame -------------------------
        # A context per check, explicitly. `browser.new_page()` was sharing the
        # session watermark between them, so the "did it animate" check ran on a
        # page that had correctly already been shown the reveal — and reported
        # that the reveal never ran. The isolation these checks depend on has to
        # be asked for rather than assumed.
        for label, viewport, extra in VIEWPORTS:
            sample_reveal(browser, url, label, viewport, failures, **extra)

        # --- it actually animated --------------------------------------------
        fresh = browser.new_context(viewport={"width": 1280, "height": 1000})
        page2 = fresh.new_page()
        page2.goto(url, wait_until="domcontentloaded")
        page2.wait_for_selector("[data-chain] [data-node]", state="visible", timeout=20000)
        # Polled rather than slept. The class is applied on mount and hydration
        # timing is not ours to predict; a fixed sleep turns a slow deploy into
        # a failed assertion about the animation.
        building = False
        for _ in range(30):
            building = page2.evaluate(
                "() => !!document.querySelector('[data-chain].chain-building')"
            )
            if building:
                break
            page2.wait_for_timeout(100)
        if not building:
            failures.append("the reveal never ran — no chain-building class was applied")
        else:
            print("reveal ran: chain-building applied after paint")

        # --- once, and not again on that page ---------------------------------
        page2.reload(wait_until="domcontentloaded")
        page2.wait_for_selector("[data-chain] [data-node]", state="visible", timeout=20000)
        page2.wait_for_timeout(700)
        again = page2.evaluate(
            "() => !!document.querySelector('[data-chain].chain-building')"
        )
        if again:
            failures.append("the reveal replayed on a second visit in the same session")
        else:
            print("second visit in the same session: no replay")

        # --- reduced motion renders it complete and instant -------------------
        quiet = browser.new_context(
            viewport={"width": 1280, "height": 1000}, reduced_motion="reduce"
        )
        calm = quiet.new_page()
        calm.goto(url, wait_until="domcontentloaded")
        calm.wait_for_selector("[data-chain] [data-node]", state="visible", timeout=20000)
        calm.wait_for_timeout(700)
        state = calm.evaluate(
            """() => {
                 const chain = document.querySelector('[data-chain]');
                 const rails = [...document.querySelectorAll('[data-chain] > li > span')];
                 return {
                   building: chain ? chain.classList.contains('chain-building') : null,
                   animating: rails.some(r => getComputedStyle(r).animationName !== 'none'),
                   steps: document.querySelectorAll('[id^="chain-"]').length,
                 };
               }"""
        )
        if state["building"]:
            failures.append("reduced motion still applied the animation class")
        if state["animating"]:
            failures.append("reduced motion still has a running animation")
        if state["steps"] < 2:
            failures.append("reduced motion lost the chain")
        if not state["building"] and not state["animating"] and state["steps"] >= 2:
            print(f"reduced motion: {state['steps']} steps, complete, no animation")

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
