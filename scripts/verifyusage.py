"""R104: the usage route equals an independent recount of the ledger.

Reads `/audit` and re-derives today's turns, cache hits and tokens under the
same rule the route states — cached turns are turns, not tokens — then compares
to `/usage`. Optionally loads the `/ask` page in a browser and requires the line
under the title to carry the route's numbers.

    python scripts/verifyusage.py [--api URL] [--site URL] [--page]
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
from datetime import UTC, datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

DEFAULT_API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
DEFAULT_SITE = "https://pashupatastra.vercel.app"


def get(api: str, path: str):
    request = urllib.request.Request(api + path, headers={"User-Agent": "pashupatastra-verify"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def compact(n: int) -> str:
    return f"{round(n / 1000)}k" if n >= 1000 else str(n)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--site", default=DEFAULT_SITE)
    parser.add_argument("--page", action="store_true", help="also check the /ask line")
    args = parser.parse_args()
    failures: list[str] = []

    reported = get(args.api, "/usage")
    today = datetime.now(UTC).date().isoformat()
    records = get(args.api, "/audit?limit=5000")
    turns = [
        r
        for r in records
        if r["kind"] == "agent_turn"
        and datetime.fromisoformat(r["at"]).astimezone(UTC).date().isoformat() == today
    ]
    cached = sum(1 for r in turns if r["detail"].get("cached"))
    tokens = sum(int(r["detail"].get("tokens") or 0) for r in turns if not r["detail"].get("cached"))

    print(f"ledger, today ({today}): {len(turns)} turns, {cached} from cache, {tokens} tokens")
    print(
        f"route:                 {reported['today']['turns']} turns, "
        f"{reported['today']['from_cache']} from cache, {reported['today']['tokens']} tokens"
    )
    if len(records) >= 5000:
        failures.append("the audit read hit its limit; the recount may be short")
    if reported["today"]["turns"] != len(turns):
        failures.append("turns differ")
    if reported["today"]["from_cache"] != cached:
        failures.append("cache hits differ")
    if reported["today"]["tokens"] != tokens:
        failures.append("tokens differ")
    if reported["spend_usd"] != 0 or not reported.get("spend_reason"):
        failures.append("spend is not zero with a reason")
    if reported["today"]["day"] != today:
        failures.append(f"route thinks today is {reported['today']['day']}")

    if args.page:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as play:
            browser = play.chromium.launch()
            page = browser.new_page()
            page.goto(f"{args.site}/ask", wait_until="networkidle")
            line = page.locator("[data-allowance]").inner_text()
            browser.close()
        expected = f"today {compact(reported['today']['tokens'])} of {compact(reported['allowance']['tokens_per_day'])} tokens"
        print(f"page: {line}")
        if expected not in line:
            failures.append(f"page line {line!r} does not carry {expected!r}")
        rate = reported["today"]["cache_hit_rate"]
        if rate is not None and not re.search(rf"{round(rate * 100)}% from cache", line):
            failures.append("page line does not carry the cache-hit rate")

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("the usage route is the ledger, counted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
