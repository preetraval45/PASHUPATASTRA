"""R109: every image on the press page was captured from the URL it depicts.

A media kit is written to be republished, so a picture that does not show what
its caption says is the one mistake here that travels. This checks the three
things that make the captions true rather than decorative:

* every image on the page has a manifest entry, so nothing appears without a
  recorded origin;
* every manifest route is reachable on this site, so each picture depicts a
  page that exists;
* the route is printed beside the image, so a reader can go and compare.

It also checks the absence that matters: the mark is not offered for download.
BRAND.md records that the artwork's origin and licensing are unestablished and
must be resolved before a public launch, and a press kit is precisely where
handing it out would do the most harm.

    python scripts/verifypress.py [--site URL]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "apps" / "web" / "lib" / "press.generated.json"
SITE = "https://pashupatastra.vercel.app"


def reachable(url: str) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": "pashupatastra-verify"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE)
    args = parser.parse_args()
    failures: list[str] = []

    if not MANIFEST.exists():
        print("FAIL  no press manifest — run python scripts/buildpress.py")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    shots = {shot["file"]: shot for shot in manifest["shots"]}
    print(f"{len(shots)} shot(s), captured {manifest['captured_at'][:10]} at {manifest['commit']}")

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 1400}).new_page()
        page.goto(f"{args.site}/press", wait_until="networkidle")
        page.wait_for_timeout(800)

        shown = page.locator("img[src^='/press/']").evaluate_all(
            "els => els.map(e => ({src: e.getAttribute('src'), loaded: e.complete && e.naturalWidth > 0}))"
        )
        text = page.inner_text("main")

        # Nothing on the page without a recorded origin.
        for image in shown:
            if image["src"] not in shots:
                failures.append(f"{image['src']} is on the page with no manifest entry")
            if not image["loaded"]:
                failures.append(f"{image['src']} did not load")

        # Nothing in the manifest missing from the page.
        for file in shots:
            if file not in {image["src"] for image in shown}:
                failures.append(f"{file} is in the manifest and not on the page")

        # Each picture depicts a page that exists, and says which.
        for shot in shots.values():
            status = reachable(args.site + shot["route"])
            if status >= 400:
                failures.append(f"{shot['file']} depicts {shot['route']}, which answers {status}")
            if shot["route"] not in text:
                failures.append(f"{shot['file']}: the page does not print {shot['route']}")
            print(f"  {shot['route']:34} {status}  {shot['file']}")

        # The absence that matters.
        offered = page.locator("a[download], a[href$='.png']:not([href^='/press/'])").count()
        if offered:
            failures.append(f"{offered} asset(s) offered for download — the mark must not be")
        if "no logo download" not in text.lower():
            failures.append("the page does not say the mark is not offered, or why")

        browser.close()

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("every image has an origin, depicts a reachable page, and names it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
