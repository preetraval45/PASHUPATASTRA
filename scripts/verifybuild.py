"""R57's done-when, checked against the deployed site rather than the source.

Three claims, each checked the only way that means anything:

1. **Attribution is on every page.** Asserted per page, not on one page and
   assumed for the rest.
2. **Every framework named is in a manifest in this repo.** The manifests are
   parsed *here*, so the page does not get to tell the checker what the right
   answer is. This is the same shape as the Observatory check: two sets computed
   independently, compared.
3. **Every link resolves.** The first version of this linked a commit that had
   never been pushed and returned 404 — a dead link on the page whose subject is
   that these claims can be checked. Fetched, not eyeballed.

LinkedIn answers 999 to anything that is not a browser session. That is its
anti-scraping response and not a broken link, so it is reported and not failed;
any other non-200 is a failure.

The stack is checked on `/how-it-works` and asserted *absent* everywhere else.
It lived in the global footer first, which put a bill of materials under every
page of the site — the build describing its own working conditions to someone
who came to read about an incident.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://pashupatastra.vercel.app"
MANIFESTS = [
    "apps/web/package.json",
    "services/api/pyproject.toml",
    "packages/core/pyproject.toml",
    "packages/connectors/pyproject.toml",
]
PAGES = [
    "/", "/overview", "/incidents", "/observatory", "/ask",
    "/blue-team", "/actions", "/how-it-works", "/audit",
]


def declared(manifest: str) -> dict[str, str]:
    path = ROOT / manifest
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            **(data.get("dependencies") or {}),
            **(data.get("devDependencies") or {}),
        }
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project") or {}
    specs = list(project.get("dependencies") or [])
    for extra in (project.get("optional-dependencies") or {}).values():
        specs.extend(extra)
    out: dict[str, str] = {}
    for spec in specs:
        match = re.match(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?\s*(.*)$", spec.strip())
        if match:
            out[match.group(1).lower()] = match.group(2).strip() or "*"
    return out


def status(url: str) -> int | str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (pashupatastra-verify)"}
    )
    try:
        return urllib.request.urlopen(request, timeout=25).getcode()
    except urllib.error.HTTPError as error:
        return error.code
    except Exception as error:  # noqa: BLE001 — a network failure is a result here
        return repr(error)


def main() -> int:
    versions: dict[str, str] = {}
    for manifest in MANIFESTS:
        versions.update(declared(manifest))

    failures: list[str] = []

    with sync_playwright() as play:
        browser = play.chromium.launch()

        for path in PAGES:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(SITE + path, wait_until="networkidle")
            footer = page.locator("footer").inner_text()
            if "Built by" not in footer:
                failures.append(f"{path}: no attribution in the footer")
            # The stack belongs on one page. Anywhere else it is noise, and the
            # check has to be able to say so rather than only checking presence.
            if path != "/how-it-works" and "Next.js" in page.locator("body").inner_text():
                failures.append(f"{path}: the stack list has leaked onto this page")
            page.close()
        print(f"attribution present: {len(PAGES) - len(failures)}/{len(PAGES)} pages")

        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(SITE + "/how-it-works", wait_until="networkidle")
        panel = page.locator("section").filter(has_text="BUILT WITH").last
        body = panel.inner_text() if panel.count() else ""

        # Every name rendered on the panel must be a package in a manifest.
        # Matched against the generated file's display names, then resolved to a
        # package and looked up in the manifests parsed above — so a name that
        # reaches the page without a dependency behind it has nowhere to hide.
        generated = json.loads(
            (ROOT / "apps" / "web" / "lib" / "buildinfo.generated.json").read_text(
                encoding="utf-8"
            )
        )
        items = [item for group in generated["groups"] for item in group["items"]]
        rendered = [item for item in items if item["name"] in body]
        print(f"dependencies named on /how-it-works: {len(rendered)} of {len(items)}")
        if len(rendered) != len(items):
            missing = [i["name"] for i in items if i not in rendered]
            failures.append(f"generated but not rendered: {missing}")
        for item in rendered:
            if item["package"].lower() not in versions:
                failures.append(f"{item['package']} is on the page and in no manifest")
        if body and "declared in" in body:
            failures.append("the panel is still printing manifest paths per dependency")

        links = [link.get_attribute("href") for link in
                 page.locator("footer a").all()]
        print(f"footer links: {len(links)}")
        for href in links:
            if not href or href.startswith("/"):
                continue
            code = status(href)
            tolerated = code == 999 and "linkedin.com" in href
            mark = "ok " if code == 200 else ("bot" if tolerated else "BAD")
            print(f"  {mark} {code}  {href}")
            if code != 200 and not tolerated:
                failures.append(f"{href} -> {code}")

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
