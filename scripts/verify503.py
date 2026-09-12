"""R99: name the 503 before fixing it.

Two reviewers saw an HTTP 503 on the first request of nearly every route,
followed by a quiet success. Nothing in the app emits one on a read route, and a
cold start hits once per container rather than once per navigation — so the
cause is not readable from the code, and this script exists to read it from the
wire instead.

It drives a real browser through a fixed list of navigations, twice over,
records every response at or above 500 with the URL and the headers that say
who answered (`x-vercel-error`, `x-vercel-id`, `apigw-requestid`, `server`),
and separately probes the API directly so a Vercel failure and an API Gateway
failure cannot be confused. Timing is recorded for every page so the "2–3
seconds of skeleton" claim is measured as well.

    python scripts/verify503.py [--site URL] [--api URL] [--rounds N]

Exit 0 means zero responses at or above 500 across the whole run. A run that
produces some is not a failure of this script — it is the finding.
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"

# The routes the reviewers named, in an order that mimics a visitor clicking
# through — each navigation is a fresh server render on a `force-dynamic` page.
ROUTES = [
    "/",
    "/incidents",
    "/incidents/INC-2026-0903",
    "/evidence/SEC-0003-a",
    "/actions",
    "/ask",
    "/search?q=ws-0148",
    "/observatory",
    "/blue-team",
    "/overview",
    "/audit",
    "/how-it-works",
]

HEADERS = ("x-vercel-error", "x-vercel-id", "x-vercel-cache", "apigw-requestid", "server", "x-amzn-errortype")


def probe_api(api: str, path: str) -> tuple[int, float, dict]:
    """One direct request to the API, with the status, the latency, and the
    headers that identify the responder."""
    request = urllib.request.Request(api + path, headers={"User-Agent": "pashupatastra-verify"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status, headers = response.status, dict(response.headers)
    except urllib.error.HTTPError as error:
        status, headers = error.code, dict(error.headers)
    elapsed = time.perf_counter() - started
    lowered = {k.lower(): v for k, v in headers.items()}
    return status, elapsed, {k: lowered.get(k) for k in HEADERS if lowered.get(k)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()

    bad: list[dict] = []
    timings: dict[str, list[float]] = {}

    # --- the API on its own, cold and then warm ------------------------------
    print("API, direct:")
    for path in ("/health", "/incidents", "/intel?limit=5", "/incidents/INC-2026-0903"):
        for attempt in range(2):
            status, elapsed, who = probe_api(args.api, path)
            print(f"  {status}  {elapsed*1000:6.0f}ms  {path}  {json.dumps(who) if who else ''}")
            if status >= 500:
                bad.append({"where": "api", "url": path, "status": status, "headers": who})

    # --- the site, through a browser ------------------------------------------
    with sync_playwright() as play:
        browser = play.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        def on_response(response):
            if response.status >= 500:
                bad.append(
                    {
                        "where": "browser",
                        "url": response.url,
                        "status": response.status,
                        "headers": {k: response.headers.get(k) for k in HEADERS if response.headers.get(k)},
                        "kind": "rsc" if "_rsc=" in response.url else "document",
                    }
                )

        page.on("response", on_response)

        for round_index in range(args.rounds):
            print(f"\nbrowser, round {round_index + 1}:")
            for route in ROUTES:
                # `load`, not `networkidle`: the overview polls `/health` on an
                # interval, so the network never goes idle and a timing taken
                # that way measures the poll. What the reviewer felt is the
                # server render, which is time-to-first-byte of the document.
                response = page.goto(args.site + route, wait_until="load", timeout=90_000)
                ttfb = page.evaluate(
                    "() => { const n = performance.getEntriesByType('navigation')[0]; "
                    "return n ? n.responseStart - n.requestStart : -1; }"
                )
                elapsed = ttfb / 1000
                timings.setdefault(route, []).append(elapsed)
                status = response.status if response else 0
                who = (
                    {k: response.headers.get(k) for k in HEADERS if response.headers.get(k)}
                    if response
                    else {}
                )
                flag = "  <-- " if status >= 500 else "      "
                print(f"  {status}  {elapsed*1000:6.0f}ms{flag}{route}  {json.dumps(who) if status >= 500 else ''}")
                # Also click a link, so the RSC prefetch/navigation path is
                # exercised rather than only full document loads.
                link = page.locator("nav a[href='/incidents']").first
                if link.count():
                    started = time.perf_counter()
                    link.click()
                    page.wait_for_url("**/incidents", timeout=90_000)
                    page.wait_for_load_state("load")
                    timings.setdefault("click:/incidents", []).append(time.perf_counter() - started)

        browser.close()

    # --- the report --------------------------------------------------------------
    print("\nmedian time to networkidle:")
    for route, samples in timings.items():
        print(f"  {statistics.median(samples)*1000:6.0f}ms  {route}  (n={len(samples)})")

    print()
    if bad:
        print(f"{len(bad)} responses at or above 500:")
        for entry in bad:
            print(f"  {json.dumps(entry, ensure_ascii=False)}")
        return 1
    print("zero responses at or above 500 across the run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
