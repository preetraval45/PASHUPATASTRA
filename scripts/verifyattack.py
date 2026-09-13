"""R75: every filled cell links to the step that fills it, and every empty
column reads as *not observed*.

The matrix is taken from the API and the page is held to it — not the other
way round — and every ref in a filled cell is followed in a browser to the
incident page, where the anchored step must exist and must carry that
technique. A cell that linked to a page rather than a step would pass a
weaker check and would leave the reader to find the claim themselves.

    python scripts/verifyattack.py [--site URL] [--api URL]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"


def get(api: str, path: str):
    request = urllib.request.Request(api + path, headers={"User-Agent": "pashupatastra-verify"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    args = parser.parse_args()
    failures: list[str] = []

    matrix = get(args.api, "/attack/matrix")
    known = [c for c in matrix["columns"] if c["known"]]
    if len(known) != 14:
        failures.append(f"{len(known)} known tactics, ATT&CK has 14")
    empty = [c["tactic"] for c in matrix["columns"] if not c["observed"]]
    filled = [(c["tactic"], cell) for c in matrix["columns"] for cell in c["techniques"]]
    print(f"{len(filled)} techniques across {len(matrix['observed_tactics'])} tactics; {len(empty)} not observed")

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
        page.goto(f"{args.site}/attack", wait_until="networkidle")

        # The page shows exactly the API's columns, in order.
        shown = page.locator("[data-matrix] > li").evaluate_all("els => els.map(e => e.dataset.tactic)")
        if shown != [c["tactic"] for c in matrix["columns"]]:
            failures.append(f"columns on the page {shown} differ from the API's")

        # Empty columns say so, in those words.
        for tactic in empty:
            cell = page.locator(f'[data-matrix] > li[data-tactic="{tactic}"]')
            text = cell.inner_text().lower()
            if "not observed" not in text:
                failures.append(f"{tactic}: empty column does not read 'not observed'")
            for forbidden in ("not covered", "not detected", "uncovered"):
                if forbidden in text:
                    failures.append(f"{tactic}: empty column claims '{forbidden}'")

        # Filled cells link to steps, and the steps exist and carry the technique.
        for tactic, cell in filled:
            technique = page.locator(f'[data-technique="{cell["id"]}"]').first
            if not technique.count():
                failures.append(f"{cell['id']} is in the API and not on the page")
                continue
            hrefs = technique.locator("a[href^='/incidents/']").evaluate_all(
                "els => els.map(e => e.getAttribute('href'))"
            )
            if len(hrefs) != len(cell["refs"]):
                failures.append(f"{cell['id']}: {len(hrefs)} links for {len(cell['refs'])} refs")
            for href in hrefs:
                target = browser.new_page()
                target.goto(args.site + href, wait_until="networkidle")
                anchor = href.split("#", 1)[1] if "#" in href else ""
                step = target.locator(f"#{anchor}") if anchor else target.locator("nothing")
                if not anchor or not step.count():
                    failures.append(f"{cell['id']}: {href} lands on no step")
                elif cell["id"] not in step.inner_text():
                    failures.append(f"{cell['id']}: step at {href} does not carry it")
                target.close()
            print(f"  {tactic} / {cell['id']}: {len(hrefs)} step link(s) followed")

        browser.close()

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("every filled cell lands on its step; every empty column says not observed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
