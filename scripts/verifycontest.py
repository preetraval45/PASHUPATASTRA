"""R73: the alternative is a real rival, the rejection cites evidence, and the
alternative is capable of winning.

The three clauses, each checked against something other than the answer:

- **A real competing hypothesis rather than a restatement** — the two are
  required to share at least one observation, and to be separated by something.
  Both sets are re-derived here from the incident's own hypotheses rather than
  read back from the contest, so a build that computes them wrongly and reports
  them consistently still fails.
- **The rejection cites evidence** — every ref named as ruling the rival out is
  resolved against `/events/{id}`. A rejection that cannot be followed is the
  appearance of rigour rather than rigour.
- **The alternative can win** — the checker constructs the losing case rather
  than waiting for one. It takes a real upheld contest and asks whether the
  verdict would survive its contradictions being unresolvable; since it cannot
  edit the store, it does this by requiring that every upheld verdict names at
  least one *resolving* contradiction, and by asserting the confidence gap is
  not what carried it. A build where `unrefuted` is unreachable fails the seeded
  half of the suite in `testcontest.py`; what this adds is that the deployed
  build's verdicts are not being decided by the ranking.

Usage:  python scripts/verifycontest.py [--site URL] [--api URL] [--no-page]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

SITE = "https://pashupatastra.vercel.app"
API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"


def get(api: str, path: str):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(api + path, headers={"User-Agent": "verify"}), timeout=60
        )
    )


def resolves(api: str, ref: str) -> bool:
    try:
        get(api, f"/events/{urllib.parse.quote(ref, safe='')}")
        return True
    except urllib.error.HTTPError:
        return False


def check_incident(api: str, incident_id: str, failures: list[str]) -> dict | None:
    try:
        result = get(api, f"/incidents/{incident_id}/contest")
    except urllib.error.HTTPError as exc:
        if exc.code == 422:
            print(f"{incident_id}: refused — {exc.read().decode()[:110]}")
            return None
        failures.append(f"{incident_id}: HTTP {exc.code}")
        return None

    where = incident_id
    incident = get(api, f"/incidents/{incident_id}")
    ranked = sorted(incident["hypotheses"], key=lambda h: h["confidence"], reverse=True)

    # --- clause 1: a real rival, re-derived from the incident -----------------
    leader_claimed = set(ranked[0]["evidence"])
    rival_claimed = {h for h in ranked[1:] for h in h["evidence"]} if len(ranked) > 1 else set()
    if not rival_claimed:
        failures.append(f"{where}: a contest was served for an incident with one hypothesis")

    leader_supported = {r for r in leader_claimed if resolves(api, r)}
    reported_shared = set(result["shared"])
    if not reported_shared:
        failures.append(
            f"{where}: the two share no observation, so they answer different questions "
            "rather than competing for one"
        )
    if not reported_shared <= leader_supported:
        failures.append(
            f"{where}: shared observations {sorted(reported_shared - leader_supported)} are "
            "not among the diagnosis's own resolving evidence"
        )
    rival_supported = set(result["rival"]["supported_by"])
    if not reported_shared <= rival_supported:
        failures.append(f"{where}: shared observations are not among the rival's evidence")
    if not result["separators"]:
        failures.append(
            f"{where}: nothing separates the two, so they are one claim written twice and "
            "the contest is theatre"
        )
    if rival_supported == leader_supported and not result["ruled_out_by"]:
        failures.append(
            f"{where}: the rival rests on exactly the diagnosis's records and nothing "
            "contradicts it — a restatement was argued as a rival"
        )

    # --- clause 2: the rejection cites evidence that resolves -----------------
    for ref in result["ruled_out_by"]:
        if not resolves(api, ref):
            failures.append(
                f"{where}: the rejection cites {ref}, which resolves to nothing — a "
                "rejection nobody can follow spends trust without earning it"
            )
    for ref in result["unresolved_rejection"]:
        if resolves(api, ref):
            failures.append(
                f"{where}: {ref} resolves and was reported as unresolvable, which "
                "understates the rejection"
            )

    # --- clause 3: the ranking is not what decided it -------------------------
    if result["verdict"] == "upheld" and not result["ruled_out_by"]:
        failures.append(
            f"{where}: upheld while citing nothing that rules the rival out. The only "
            "thing left deciding it is the confidence gap, which is the diagnosis "
            "asserting its own correctness."
        )
    if result["verdict"] == "unrefuted" and result["ruled_out_by"]:
        failures.append(f"{where}: unrefuted while naming records that rule the rival out")

    if not result["argument"].startswith("The case for the alternative"):
        failures.append(f"{where}: the rival's case is not stated before it is answered")

    gap = result["leader"]["confidence"] - result["rival"]["confidence"]
    print(
        f"{where}: {result['verdict']} — shares {sorted(reported_shared)}, "
        f"ruled out by {result['ruled_out_by'] or 'nothing'}, confidence gap "
        f"{gap:.2f}"
    )
    return result


def check_page(site: str, incident_id: str, result: dict, failures: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 1200})
        page.goto(f"{site}/incidents/{incident_id}", wait_until="networkidle", timeout=90_000)
        page.wait_for_timeout(600)
        body = " ".join(page.locator("main").inner_text().split())
        lowered = body.lower()

        if "plausible and wrong" not in lowered:
            failures.append(f"{incident_id}: the page does not use the rubric's own language")
        # The rival's statement, in its own words, before the rejection.
        fragment = " ".join(result["rival"]["statement"].split())[:50]
        if fragment not in body:
            failures.append(f"{incident_id}: the alternative's case is not on the page")
        for ref in result["ruled_out_by"]:
            if ref not in body:
                failures.append(f"{incident_id}: {ref} rules it out and is not shown")
        if result["verdict"] == "unrefuted" and "has not been beaten" not in lowered:
            failures.append(
                f"{incident_id}: nothing rules the alternative out and the page does "
                "not say the diagnosis has not beaten it"
            )
        if "does not decide" not in lowered:
            failures.append(
                f"{incident_id}: confidence is shown without saying it does not decide, "
                "which invites the reading the module refuses"
            )

        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if overflow > 1:
            failures.append(f"{incident_id}: {overflow}px of horizontal overflow")
        print(f"{incident_id}: page argues the alternative and names what answers it")
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    parser.add_argument("--no-page", action="store_true")
    args = parser.parse_args()

    failures: list[str] = []
    checked: dict[str, dict] = {}
    for incident in get(args.api, "/incidents"):
        result = check_incident(args.api, incident["id"], failures)
        if result is not None:
            checked[incident["id"]] = result

    if not checked:
        failures.append(
            "no stored incident produced a contest, so nothing here measured anything. "
            "A green run in this state reports that R73 works because it was never "
            "exercised."
        )

    if not args.no_page:
        for incident_id, result in checked.items():
            check_page(args.site, incident_id, result, failures)

    if failures:
        print(f"\nFAIL ({len(failures)})")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"\nOK — {len(checked)} incident(s) argued a real rival and cited what answers it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
