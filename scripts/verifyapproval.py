"""R65: the approval panel explains the tier with the numbers the tier came from.

Two clauses, checked two different ways.

**"It cannot disagree with the tier."** Checked by comparing the rendered panel
against a verdict the checker obtains from the API itself, for the same action
and the same incident numbers the page evaluates. The page does not get to tell
the checker what it was allowed to say — an earlier version of this script read
the steps off the page and checked they were internally consistent, which is a
test that a page contradicting the engine passes comfortably.

**"Distinguishable without colour."** Checked with colour removed, not by
reading class names. The page is rendered through a grayscale filter and the
landed tier is required to be identifiable from what survives: exactly one cell
marked as current, carrying the tier's name as text, a marker a reader can see,
and a heavier border than its neighbours. Two of the four tiers share the `▲`
glyph, so the glyph alone was never going to carry this.

The API half runs against a matrix of contexts rather than the one the incident
happens to produce: the interesting case — a tier the score alone does not
explain — is not reachable from the demo incidents, and a checker that only
looks at what the demo shows would report green on a panel that has never had
to explain anything.

Usage:  python scripts/verifyapproval.py [--site URL] [--api URL]
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

TIER_LABEL = {
    "autonomous": "Autonomous",
    "approval": "Approval required",
    "senior": "Senior approval",
    "denied": "Never autonomous",
}

# Contexts chosen to reach a tier by every route the engine has: the score
# alone, a blast radius that escalates, an irreversibility that denies whatever
# the score said, and an agent limit that overrides both.
MATRIX = [
    {"action_id": "restart_service"},
    {"action_id": "restart_service", "blast_radius_entities": 7, "blast_radius_users": 2400},
    {"action_id": "rollback_deployment", "diagnostic_confidence": 0.3},
    {"action_id": "modify_db_config", "blast_radius_entities": 12},
    {"action_id": "force_password_reset"},
    {"action_id": "delete_infrastructure"},
    {"action_id": "isolate_host", "agent_risk_limit": 20},
]


def get(api: str, path: str):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(api + path, headers={"User-Agent": "verify"}), timeout=45
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
            timeout=45,
        )
    )


def check_engine(api: str, failures: list[str]) -> None:
    """Every verdict explains itself, and the explanation lands on the tier."""
    for body in MATRIX:
        verdict = post(api, "/policy/evaluate", body)
        where = f"{body['action_id']} {json.dumps(body, sort_keys=True)}"
        steps = verdict.get("tier_reasons") or []
        if not steps:
            failures.append(f"{where}: tier {verdict['tier']} with no reasons")
            continue
        if steps[0]["rule"] != "risk_band":
            failures.append(f"{where}: first reason is {steps[0]['rule']}, not the band")
        if str(verdict["effective_risk"]) not in steps[0]["detail"]:
            failures.append(f"{where}: the band does not name the score it banded")
        if steps[-1]["to_tier"] != verdict["tier"]:
            failures.append(
                f"{where}: reasons end at {steps[-1]['to_tier']}, verdict says {verdict['tier']}"
            )
        for earlier, later in zip(steps, steps[1:]):
            if later["from_tier"] != earlier["to_tier"]:
                failures.append(f"{where}: reasons skip from {earlier['to_tier']}")
        for adjustment in verdict["adjustments"]:
            if not adjustment.get("factor"):
                failures.append(f"{where}: adjustment {adjustment['reason']!r} names no factor")

    # The case worth having the panel for: a tier the arithmetic does not
    # account for. If nothing in the matrix produces one, the check above has
    # only ever seen the easy half.
    unexplained = [
        v
        for v in (post(api, "/policy/evaluate", body) for body in MATRIX)
        if len(v.get("tier_reasons") or []) > 1
    ]
    if not unexplained:
        failures.append("no verdict in the matrix needed more than its score — nothing was tested")


def check_page(site: str, api: str, incident_id: str, failures: list[str]) -> None:
    verdict = None
    incident = get(api, f"/incidents/{incident_id}")
    actions = {a["id"]: a["base_risk"] for a in get(api, "/actions")}
    plan = sorted(incident["plan"], key=lambda s: -actions.get(s["action_id"], 0))
    if not plan:
        failures.append(f"{incident_id}: no plan, so no authorization to check")
        return

    # The same evaluation the page performs, obtained independently of it.
    verdict = post(
        api,
        "/policy/evaluate",
        {
            "action_id": plan[0]["action_id"],
            "incident_ref": incident_id,
            "blast_radius_entities": incident["impact"]["blast_radius_entities"],
            "blast_radius_users": incident["impact"]["estimated_users_affected"],
            "diagnostic_confidence": (incident["hypotheses"] or [{}])[0].get("confidence", 1),
        },
    )
    steps = verdict.get("tier_reasons") or []

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{site}/incidents/{incident_id}", wait_until="networkidle", timeout=60_000)

        panel = page.locator("section", has=page.get_by_role("heading", name="Authorization"))
        if panel.count() == 0:
            failures.append(f"{incident_id}: no authorization panel on the page")
            browser.close()
            return
        panel = panel.first
        text = panel.inner_text()

        # Every step the engine recorded is on the page, in the engine's words.
        # `inner_text` returns rendered text, and the section labels are
        # uppercased by CSS, so comparison is case-insensitive throughout —
        # verifydebrief.py lost an assertion to exactly this in R64.
        haystack = " ".join(text.split()).lower()
        for step in steps:
            needle = " ".join(step["detail"].split()).lower()
            if needle not in haystack:
                failures.append(f"{incident_id}: panel omits {step['rule']}: {step['detail']!r}")
        if steps and TIER_LABEL[verdict["tier"]].lower() not in haystack:
            failures.append(f"{incident_id}: panel does not name the tier {verdict['tier']}")

        # -- distinguishable without colour ---------------------------------
        page.add_style_tag(content="html { filter: grayscale(1) !important; }")
        current = panel.locator('[aria-current="step"]')
        if current.count() != 1:
            failures.append(
                f"{incident_id}: {current.count()} tiers marked as current, expected exactly 1"
            )
        else:
            marked = current.first.inner_text().lower()
            if TIER_LABEL[verdict["tier"]].lower() not in marked:
                failures.append(f"{incident_id}: the marked tier is not the verdict's tier")
            if "this action" not in marked:
                failures.append(f"{incident_id}: the marked tier carries no visible marker")
            widths = panel.locator("ol li[aria-current], ol li").evaluate_all(
                "els => els.map(e => [e.getAttribute('aria-current'),"
                " parseFloat(getComputedStyle(e).borderTopWidth)])"
            )
            here = [w for a, w in widths if a == "step"]
            others = [w for a, w in widths if a != "step" and w > 0]
            if here and others and min(here) <= max(others):
                failures.append(
                    f"{incident_id}: the current tier is not distinguishable by border weight "
                    f"({here} vs {others}) — with colour removed, nothing marks it"
                )

        # -- and it still fits a phone ---------------------------------------
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(200)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if overflow > 1:
            failures.append(f"{incident_id}: {overflow}px of horizontal scroll at 390px")

        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    args = parser.parse_args()

    failures: list[str] = []
    check_engine(args.api, failures)

    incidents = [i["id"] for i in get(args.api, "/incidents") if i.get("plan")]
    if not incidents:
        failures.append("no incident carries a plan, so no approval surface renders anywhere")
    for incident_id in incidents[:3]:
        check_page(args.site, args.api, incident_id, failures)

    if failures:
        print(f"FAIL ({len(failures)})")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"OK — {len(MATRIX)} verdicts explain themselves, {len(incidents[:3])} panels agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
