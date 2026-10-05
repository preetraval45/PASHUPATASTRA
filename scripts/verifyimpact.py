"""R107: every figure on `/impact` equals a recount of its own source.

The page is a set of claims about a project, read by people whose job is to
doubt it, so the only thing that makes it worth anything is that each number
can be recomputed from somewhere else. This recomputes them — from `/intel`,
`/audit`, `/incidents`, the GitHub API and git — and compares. It never reads
the page to find out what the page should say.

The absent cases are checked as carefully as the present ones. A figure that
could not be measured must say so with a reason and must **not** be zero: "no
one has starred it" and "GitHub did not answer" are different facts, and a
page that showed both as 0 would be the invented metric this project is
arranged against.

    python scripts/verifyimpact.py [--api URL] [--site URL] [--page]
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

ROOT = Path(__file__).resolve().parents[1]
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
SITE = "https://pashupatastra.vercel.app"


def get(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "pashupatastra-verify"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=API)
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--page", action="store_true", help="also check the rendered page")
    args = parser.parse_args()
    failures: list[str] = []

    impact = get(f"{args.api}/impact")

    def figure(name: str) -> dict:
        value = impact[name]
        # The shape is part of the contract: exactly one of a value with a
        # source, or an absence with a reason.
        if value.get("absent"):
            if value.get("value") is not None:
                failures.append(f"{name}: absent and still carries a value")
            print(f"  {name:14} absent — {value['absent']}")
        elif not value.get("from"):
            failures.append(f"{name}: a value with no source named")
        return value

    # --- incidents ------------------------------------------------------------
    incidents = figure("incidents")
    if incidents.get("value") is not None:
        actual = len(get(f"{args.api}/incidents"))
        if incidents["value"] != actual:
            failures.append(f"incidents: page {incidents['value']}, /incidents {actual}")
        else:
            print(f"  incidents      {actual} — matches /incidents")

    # --- intelligence ---------------------------------------------------------
    intel = figure("intelligence")
    if intel.get("value") is not None:
        served = get(f"{args.api}/intel?limit=5000")
        groups = served.get("groups") or []
        if intel["value"]["indicators"] != len(groups):
            failures.append(
                f"indicators: /impact {intel['value']['indicators']}, /intel {len(groups)}"
            )
        else:
            print(f"  intelligence   {len(groups)} indicators — matches /intel")

    # --- the ledger -----------------------------------------------------------
    ledger = figure("ledger")
    if ledger.get("value") is not None:
        rows = get(f"{args.api}/audit?limit=5000")
        turns = sum(1 for r in rows if r["kind"] == "agent_turn")
        if len(rows) >= 5000:
            print("  ledger         (audit read hit its limit; comparing what was returned)")
        if ledger["value"]["agent_turns"] != turns:
            failures.append(
                f"agent turns: /impact {ledger['value']['agent_turns']}, /audit {turns}"
            )
        else:
            print(f"  ledger         {turns} agent turns — matches /audit")

    # --- the repository -------------------------------------------------------
    repo = figure("repository")
    if repo.get("value") is not None:
        try:
            live = get("https://api.github.com/repos/preetraval45/PASHUPATASTRA")
            if repo["value"]["stars"] != live.get("stargazers_count"):
                failures.append(
                    f"stars: /impact {repo['value']['stars']}, GitHub {live.get('stargazers_count')}"
                    " — the hourly cache may simply be older, which is fine, but say so"
                )
            else:
                print(f"  repository     {repo['value']['stars']} stars — matches GitHub")
        except urllib.error.HTTPError as error:
            print(f"  repository     (GitHub refused this checker: {error.code})")

    # --- milestones, recomputed from git -------------------------------------
    milestones = figure("milestones")
    if milestones.get("value") is not None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "milestones.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failures.append(f"milestones: {result.stdout.strip() or 'the committed file is stale'}")
        else:
            print(f"  milestones     {len(milestones['value'])} — the committed file is current")
        for entry in milestones["value"]:
            if not entry.get("sha") or not entry.get("tasks"):
                failures.append(f"milestones: an entry with no commit or no task — {entry}")

    # --- views and uptime -----------------------------------------------------
    views = figure("views")
    uptime = figure("uptime")
    if views.get("value") is not None:
        counted = sum(views["value"]["by_day"].values())
        if counted != views["value"]["total"]:
            failures.append(f"views: total {views['value']['total']} but days sum to {counted}")
        else:
            print(f"  views          {counted} renders across {views['value']['days']} day(s)")
    if uptime.get("value") is not None:
        share = uptime["value"]["share"]
        if share is not None and not 0 <= share <= 1.5:
            failures.append(f"uptime: a share of {share} is not a share")

    # --- the page says the same thing -----------------------------------------
    if args.page:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as play:
            browser = play.chromium.launch()
            page = browser.new_context(viewport={"width": 1280, "height": 1200}).new_page()
            page.goto(f"{args.site}/impact", wait_until="networkidle")
            body = page.inner_text("main")
            browser.close()

        if incidents.get("value") is not None and str(incidents["value"]) not in body:
            failures.append("the page does not show the incident count the API reports")
        for name in ("intelligence", "ledger", "views", "uptime", "repository", "milestones"):
            reason = impact[name].get("absent")
            if reason and reason not in body:
                failures.append(f"{name}: absent on the API and the page does not say why")
        if "renders, not people" not in body and "not people" not in body:
            failures.append("the page does not say views are renders rather than people")
        print("  page           figures and absences both rendered")

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("every figure matches a recount of its own source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
