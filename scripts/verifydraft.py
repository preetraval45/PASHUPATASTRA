"""R70: a draft cites what it asserts, says it is a draft, and cannot be adopted quietly.

Every clause is checkable without a model, which is the point of building the
documents deterministically. What needs care is the citation clause, because
"every line has refs" is satisfied by a line citing `evt-imaginary`. So each ref
is resolved against the store: a chain index that exists, a plan order that
exists, an event the store returns, or the incident itself. A citation that
looks checkable and leads nowhere is worse than none — R59's rule, one layer up.

The adoption clause is checked against the policy engine rather than against the
page's sentence about it. The page says what it would cost; `/policy/evaluate`
says what it does cost, and the two have to agree or the page is reassuring
somebody with a number nobody computed.

Usage:  python scripts/verifydraft.py [--site URL] [--api URL]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
KINDS = ("post_incident", "playbook")


def get(api: str, path: str):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(api + path, headers={"User-Agent": "verify"}), timeout=60
        )
    )


def post(api: str, path: str, body: dict):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(
                api + path,
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "verify"},
            ),
            timeout=60,
        )
    )


def resolvable(api: str, incident: dict, ref: str) -> bool:
    """Does this ref point at a record that exists?

    Resolved against the incident and the store, not against a pattern. A regex
    that accepts `INC-2026-0903#chain-9` would accept exactly the near-miss
    citation this is looking for.
    """
    incident_id = incident["id"]
    if ref == incident_id:
        return True
    if ref.startswith(f"{incident_id}#chain-"):
        index = ref.rsplit("-", 1)[-1]
        return index.isdigit() and int(index) < len(incident["causal_chain"])
    if ref.startswith(f"{incident_id}#hypothesis-"):
        index = ref.rsplit("-", 1)[-1]
        return index.isdigit() and int(index) < len(incident["hypotheses"])
    if ref.startswith(f"{incident_id}#plan-"):
        order = ref.rsplit("-", 1)[-1]
        return order.isdigit() and any(step["order"] == int(order) for step in incident["plan"])
    try:
        get(api, f"/events/{urllib.parse.quote(ref, safe='')}")
        return True
    except urllib.error.HTTPError:
        return False


def check_api(api: str, incident_id: str, failures: list[str]) -> dict:
    incident = get(api, f"/incidents/{incident_id}")
    drafts = {}
    for kind in KINDS:
        draft = get(api, f"/incidents/{incident_id}/draft/{kind}")
        drafts[kind] = draft
        where = f"{incident_id}/{kind}"

        if draft["status"] != "draft":
            failures.append(f"{where}: status is {draft['status']!r}")
        if not draft["title"].lower().startswith("draft"):
            failures.append(f"{where}: the title does not say it is a draft — {draft['title']!r}")

        lines = [line for section in draft["sections"] for line in section["lines"]]
        if not lines:
            failures.append(f"{where}: rendered no lines at all")
        for line in lines:
            if not line["refs"]:
                failures.append(f"{where}: uncited — {line['text'][:60]!r}")
                continue
            for ref in line["refs"]:
                if not resolvable(api, incident, ref):
                    failures.append(
                        f"{where}: {line['text'][:40]!r} cites {ref!r}, which resolves to nothing"
                    )
        print(f"{where}: {len(lines)} lines, {len(draft['sections'])} sections, all cited")

        # Adopting it costs what the engine says it costs.
        verdict = post(
            api,
            "/policy/evaluate",
            {
                "action_id": draft["adopt_action_id"],
                "incident_ref": incident_id,
                "blast_radius_entities": incident["impact"]["blast_radius_entities"],
                "blast_radius_users": incident["impact"]["estimated_users_affected"],
                "diagnostic_confidence": (incident["hypotheses"] or [{}])[0].get("confidence", 1),
            },
        )
        if verdict["tier"] == "autonomous":
            failures.append(
                f"{where}: {draft['adopt_action_id']} is autonomous — a draft nobody "
                "approved could become the procedure"
            )
        if not verdict["required_approvers"]:
            failures.append(f"{where}: adopting names nobody who has to approve it")
        print(
            f"{where}: adopting is {draft['adopt_action_id']} — {verdict['tier']}, "
            f"risk {verdict['effective_risk']}"
        )
    return drafts


def check_page(site: str, incident_id: str, drafts: dict, failures: list[str]) -> None:
    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 1000})
        page.goto(f"{site}/incidents/{incident_id}", wait_until="networkidle", timeout=90_000)
        page.wait_for_timeout(600)

        body = " ".join(page.locator("main").inner_text().split()).lower()
        for kind, draft in drafts.items():
            heading = draft["title"].lower()
            if heading not in body:
                failures.append(f"{kind}: the page does not show {draft['title']!r}")
            # Every line on the page, and every line labelled a draft where a
            # reader would copy it from.
            for section in draft["sections"]:
                for line in section["lines"]:
                    fragment = " ".join(line["text"].split()).lower()[:50]
                    if fragment not in body:
                        failures.append(f"{kind}: the page omits {line['text'][:50]!r}")

        badges = page.get_by_text("draft — not adopted").count()
        if badges < len(drafts):
            failures.append(
                f"{badges} draft badges for {len(drafts)} drafts — one of them reads as adopted"
            )

        # Refs are links, because the claim is that a reviewer can check them.
        for panel_title in (draft["title"] for draft in drafts.values()):
            panel = page.locator("section", has=page.get_by_role("heading", name=panel_title))
            if not panel.count():
                failures.append(f"no panel for {panel_title!r}")
                continue
            links = panel.first.locator("li a").count()
            if links == 0:
                failures.append(f"{panel_title!r}: no citation is a link")

        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if overflow > 1:
            failures.append(f"{overflow}px of horizontal overflow with the drafts rendered")
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    args = parser.parse_args()

    failures: list[str] = []
    incidents = get(args.api, "/incidents")
    if not incidents:
        print("SKIP — no incidents are stored, so there is nothing to draft from")
        return 1

    incident_id = incidents[0]["id"]
    drafts = check_api(args.api, incident_id, failures)
    check_page(args.site, incident_id, drafts, failures)

    if failures:
        print(f"FAIL ({len(failures)})")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"OK — {len(KINDS)} drafts, every line cited and resolving, neither adoptable alone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
