"""R115: no live indicator from a feed is served by the site.

Content filters classify a page by what it carries, and the Observatory used to
carry malware hosts and botnet C2 addresses verbatim. This reads every
reachable indicator the API holds — the live values, from the source rather
than from the page — then fetches every route in the sitemap plus every
Observatory filter, and fails if any of those values appears in a response
body in its live form: HTML, RSC payload, attribute, or React key.

It also checks the other half: that the Observatory still shows them, defanged,
so a pass cannot be produced by a page that simply stopped rendering the feed.

    python scripts/verifydefang.py [--site URL] [--api URL]
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.request

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"

REACHABLE = {"url", "ip", "domain", "host", "hostname"}

# The advisory links stay live on purpose: they point at the publisher's page
# *about* an indicator (`feodotracker.abuse.ch/browse/host/<ip>/`), which is
# how a reader checks a claim, and a filter sees a link to abuse.ch rather than
# to the indicator. A value inside one of these is not a leak.
PUBLISHERS = re.compile(
    r"https?://(?:[a-z0-9-]+\.)*(?:abuse\.ch|cisa\.gov|nist\.gov|haveibeenpwned\.com|ransomware\.live)/[^\s\"'<>\\]*",
    re.IGNORECASE,
)


def fetch(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "pashupatastra-verify"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def refang(value: str) -> str:
    value = value.replace("[.]", ".").replace("[@]", "@")
    return re.sub(r"^h[x]{2}(ps?)://", r"htt\1://", re.sub(r"^fxp://", "ftp://", value), flags=re.I)


def live_values(api: str) -> tuple[list[str], list[str]]:
    status, body = fetch(f"{api}/intel?limit=200")
    if status != 200:
        raise SystemExit(f"api /intel answered {status}")
    intel = json.loads(body)
    values: list[str] = []
    for group in intel["groups"]:
        kind, _, rest = group["entity_key"].partition(":")
        feed_type, _, value = rest.partition(":")
        if feed_type.lower() in REACHABLE and value:
            # The API may already send the value defanged; what must not be
            # served is the live form, so that is what is searched for.
            value = refang(value)
            host = re.sub(r"^[a-z]+://", "", value).split("/")[0]
            # `ip:port:1.2.3.4:443` — the address is what a scanner matches.
            for part in host.split(":"):
                if "." in part:
                    values.append(part)
    return sorted(set(values)), intel["sources"]


def routes(site: str, sources: list[str]) -> list[str]:
    status, body = fetch(f"{site}/sitemap.xml")
    paths = re.findall(r"<loc>([^<]+)</loc>", body) if status == 200 else []
    # The sitemap carries the canonical host; crawl the site under test.
    found = [re.sub(r"^https?://[^/]+", site, path) for path in paths]
    found += [f"{site}/observatory?source={name}" for name in sources]
    return sorted(set(found + [f"{site}/observatory"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    args = parser.parse_args()
    site = args.site.rstrip("/")

    values, sources = live_values(args.api)
    if not values:
        print("FAIL  the API holds no reachable indicators — nothing to prove absent")
        return 1
    print(f"{len(values)} live indicators held by the API")

    failures = 0
    for url in routes(site, sources):
        status, body = fetch(url)
        served = PUBLISHERS.sub("", body)
        leaked = [value for value in values if value in served]
        mark = "ok  " if status == 200 and not leaked else "FAIL"
        if mark == "FAIL":
            failures += 1
        detail = f"leaks {', '.join(leaked[:3])}" if leaked else ""
        print(f"{mark}  {status}  {url.removeprefix(site) or '/'}  {detail}")

    _, page = fetch(f"{site}/observatory")
    shown = [value for value in values if value.replace(".", "[.]") in page]
    if shown:
        print(f"ok    the Observatory still shows {len(shown)} of them, defanged")
    else:
        print("FAIL  no defanged indicator on the Observatory — a pass would be vacuous")
        failures += 1

    print("PASS" if not failures else f"{failures} FAILED")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
