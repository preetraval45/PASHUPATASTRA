"""Crawl the deployed site and report what is actually broken.

The per-task checks each verify one claim. This one asks the question none of
them do: **does the whole thing hold together after everything that landed?**

It follows every internal link it finds, so a page nothing links to is not
checked and a page linked from three places is checked once. Three classes of
failure, all of which have shipped here before:

- a link to a page that does not exist — R52's audit trail was unreachable and
  the overview's incident cards pointed at the list rather than the incident
- a page that renders but throws in the browser — a server component that
  swallows an error still returns 200
- a page that renders *empty*, which is the one a status code cannot see. Every
  page is checked for content, because "200 OK and nothing on it" is how the
  feed bugs presented.
"""

from __future__ import annotations

import io
import sys
from collections import deque
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"

# Words that mean the page gave up.
#
# `no such page` is the important one and the reason a status code is not
# enough: `notFound()` under dynamic rendering returns **HTTP 200** with the
# not-found body, so a broken link is indistinguishable from a working one to
# anything that only reads status. That is how `/evidence/INC-2026-0901` was
# linked from every hypothesis on the site without any check noticing.
EMPTY_SIGNS = (
    "no such page",
    "api unreachable",
    "something went wrong",
    "application error",
)

MIN_CONTENT = 200
"""Characters of visible text in <main>. A page under this rendered its chrome
and nothing else, which is what an empty feed or a failed fetch looks like."""

DELIBERATELY_SPARSE = {"/search"}
"""Pages whose empty state is the correct answer. `/search` with no query says
so in words; measuring it against a length threshold tests nothing about it."""


def internal(href: str, base: str) -> str | None:
    if not href or href.startswith(("#", "mailto:", "tel:")):
        return None
    url = urljoin(base, href)
    if urlparse(url).netloc != urlparse(SITE).netloc:
        return None
    return url.split("#")[0].rstrip("/") or SITE


def main() -> int:
    failures: list[str] = []
    seen: set[str] = set()
    queue: deque[tuple[str, str]] = deque([(SITE, "(entry)")])
    checked = 0

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on(
            "console",
            lambda msg: errors.append(msg.text) if msg.type == "error" else None,
        )

        while queue:
            url, came_from = queue.popleft()
            if url in seen:
                continue
            seen.add(url)

            errors.clear()
            response = page.goto(url, wait_until="networkidle")
            status = response.status if response else 0
            path = url.replace(SITE, "") or "/"

            if status >= 400:
                failures.append(f"{path}: HTTP {status} (linked from {came_from})")
                continue

            body = page.locator("main").inner_text()
            note = ""
            if len(body.strip()) < MIN_CONTENT and path not in DELIBERATELY_SPARSE:
                failures.append(f"{path}: rendered {len(body.strip())} chars — effectively empty")
                note = "  EMPTY"
            for sign in EMPTY_SIGNS:
                if sign in body.lower():
                    failures.append(f"{path}: shows {sign!r}")
                    note = "  ERROR TEXT"
            if errors:
                failures.append(f"{path}: browser errors {errors[:2]}")
                note = "  JS ERROR"

            checked += 1
            print(f"  {status}  {len(body.strip()):>6} chars  {path}{note}")

            for link in page.locator("a").all():
                target = internal(link.get_attribute("href") or "", url)
                if target and target not in seen:
                    queue.append((target, path))

        browser.close()

    print(f"\n{checked} pages crawled")
    if failures:
        print()
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("no broken links, no empty pages, no browser errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
