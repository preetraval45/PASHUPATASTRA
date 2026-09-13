"""R77: every rule names its incident and its author, and the two kinds are
told apart on the page by more than a word.

Read from the API first and the page held to it. For every rule: the author
line names a person or `sati`, the incident is named and its link resolves.
For the two kinds: the marker and the border are measured — a dashed border
for a draft, a solid one for a person's rule — through a grayscale filter, so
the distinction survives colour being taken away. A page that distinguished
them by hue alone would pass a text check and fail a reader who cannot see
the hue.

    python scripts/verifydetections.py [--site URL] [--api URL]
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

    library = get(args.api, "/detections")
    print(f"{library['count']} rules: {library['drafted']} drafted, {library['written']} written")
    if library["written"] < 1 or library["drafted"] < 1:
        failures.append("both kinds must be present for the distinction to be checked")

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
        page.goto(f"{args.site}/detections", wait_until="networkidle")
        page.add_style_tag(content="html { filter: grayscale(1) !important; }")

        styles: dict[str, set[str]] = {"agent": set(), "human": set()}
        for rule in library["rules"]:
            rows = page.locator(f'[data-rule="{rule["rule_id"]}"]')
            if not rows.count():
                failures.append(f"{rule['rule_id']} is in the API and not on the page")
                continue
            row = rows.first
            kind = row.get_attribute("data-author-kind")
            if kind != rule["author"]["kind"]:
                failures.append(f"{rule['rule_id']}: page says {kind}, API says {rule['author']['kind']}")
            author = row.locator("[data-author]").inner_text()
            if rule["author"]["name"] not in author:
                failures.append(f"{rule['rule_id']}: author line {author!r} does not name {rule['author']['name']}")
            if rule["author"]["kind"] == "human" and author.startswith("drafted"):
                failures.append(f"{rule['rule_id']}: a person's rule is labelled drafted")
            text = row.inner_text()
            for incident in rule["incidents"]:
                if incident not in text:
                    failures.append(f"{rule['rule_id']}: does not name {incident}")
            styles[rule["author"]["kind"]].add(row.evaluate("e => getComputedStyle(e).borderStyle"))

        # The kinds differ in border style, not only in colour.
        if styles["agent"] & styles["human"]:
            failures.append(f"drafted and written share a border style: {styles}")
        print(f"  border styles — drafted {sorted(styles['agent'])}, written {sorted(styles['human'])}")

        # Every incident link from the page resolves to the incident.
        hrefs = page.locator("a[href^='/incidents/']").evaluate_all(
            "els => [...new Set(els.map(e => e.getAttribute('href')))]"
        )
        for href in hrefs:
            probe = browser.new_page()
            probe.goto(args.site + href, wait_until="networkidle")
            if "no such page" in probe.inner_text("main").lower():
                failures.append(f"{href} is no such page")
            probe.close()
        print(f"  {len(hrefs)} incident link(s) followed")

        # A written rule's own page names its author and shows the document.
        for rule in library["rules"]:
            if rule["author"]["kind"] != "human":
                continue
            probe = browser.new_page()
            probe.goto(f"{args.site}/detections/{rule['rule_id']}", wait_until="networkidle")
            body = probe.inner_text("main")
            if rule["author"]["name"] not in body or "title:" not in body:
                failures.append(f"{rule['rule_id']}: its page lacks the author or the document")
            probe.close()

        browser.close()

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("every rule names its incident and its author, and the two kinds are told apart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
