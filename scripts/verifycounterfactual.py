"""R72: the estimate comes from stored records, says it is an estimate, and
refuses the question the timeline cannot support.

Each clause is checked against something other than the answer itself:

- **Derived from stored records** — every step the estimate claims to have
  pre-empted is re-derived here. Its refs are resolved against `/events/{id}`,
  the event's own `occurred_at` is compared with the moment intervened at, and
  the step's entity is checked against a `blast_radius` walk taken independently
  through `/entity/...`. An estimate whose prevented step is not actually later,
  or not actually downstream, fails — those are the two ways this feature goes
  wrong while still returning a plausible number.
- **Presented as an estimate with its basis stated** — the summary has to say so
  and the basis has to carry the assumptions the records cannot settle. A number
  without them reads as a measurement.
- **Refuses rather than guesses** — the checker asks a question the timeline
  cannot support (a moment before the first record of the entity) and requires a
  422. A build that answers it has lost the constraint that separates this from
  a wish, and would do so silently.

Usage:  python scripts/verifycounterfactual.py [--site URL] [--api URL] [--no-page]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

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


def counterfactual(api: str, incident_id: str, entity_key: str, at: str):
    query = urllib.parse.urlencode({"entity_key": entity_key, "at": at})
    return get(api, f"/incidents/{incident_id}/counterfactual?{query}")


def reach_of(api: str, entity_key: str, failures: list[str]) -> set[str] | None:
    """The blast radius walked through the public entity view.

    Taken from a different endpoint than the counterfactual used, on purpose. If
    both read the same computation the check only proves it is self-consistent,
    which it would be even if the walk were wrong.

    `/entities/` takes a `:path` parameter, so the key goes in unencoded — an
    entity key contains colons and a network-flow key contains a slash, and
    percent-encoding them produces a 404.

    Returns None rather than an empty set when the entity cannot be read. They
    are not the same thing: an empty set means nothing depends on this, and None
    means the check could not be made. Collapsing the two made every downstream
    step look fabricated — the checker reporting its own blind spot as the
    system lying, which is worse than not checking at all.
    """
    try:
        return set((get(api, f"/entities/{entity_key}").get("blast_radius") or {}).get(
            "affected"
        ) or [])
    except urllib.error.HTTPError as exc:
        failures.append(
            f"cannot walk {entity_key} independently — /entities returned "
            f"HTTP {exc.code}, so whether the estimate's reach is real went unchecked"
        )
        return None


def check_incident(api: str, incident_id: str, failures: list[str]) -> dict | None:
    timeline = get(api, f"/incidents/{incident_id}/timeline")
    steps = timeline["steps"]
    if len(steps) < 2:
        print(f"{incident_id}: {len(steps)} timed step(s) — nothing to act earlier than")
        return None

    for step in steps:
        if not step["refs"]:
            failures.append(f"{incident_id}: step {step['index']} is timed by nothing")

    first = steps[0]
    result = counterfactual(api, incident_id, first["entity_key"], first["at"])
    where = f"{incident_id}/{first['entity_key']}"
    moment = datetime.fromisoformat(result["at"])

    # --- clause 1: every prevented step is really later, and really downstream -
    walked = reach_of(api, first["entity_key"], failures)
    downstream = None if walked is None else walked | {first["entity_key"]}
    for step in result["prevented"]:
        when = datetime.fromisoformat(step["at"])
        if when <= moment:
            failures.append(
                f"{where}: claims to have pre-empted {step['entity_key']} at "
                f"{step['at']}, which is not after {result['at']}"
            )
        if downstream is not None and step["entity_key"] not in downstream:
            failures.append(
                f"{where}: claims to have pre-empted {step['entity_key']}, which an "
                "independent blast-radius walk says is not downstream — later is not "
                "the same as caused by"
            )
        for ref in step["refs"]:
            try:
                event = get(api, f"/events/{urllib.parse.quote(ref, safe='')}")
            except urllib.error.HTTPError:
                failures.append(f"{where}: prevented step cites {ref}, which resolves to nothing")
                continue
            observed = event.get("occurred_at")
            if observed and datetime.fromisoformat(observed) <= moment:
                failures.append(
                    f"{where}: {ref} was observed at {observed}, at or before the "
                    "moment intervened at, so the step it dates was not pre-empted"
                )

    # The other half. A later step outside the reach must be reported, not counted.
    if downstream is not None:
        for step in result["unavoidable"]:
            if step["entity_key"] in downstream:
                failures.append(
                    f"{where}: {step['entity_key']} is downstream and was filed as "
                    "unavoidable, which understates the estimate"
                )
        if set(result["avoided_entities"]) - downstream:
            failures.append(f"{where}: avoided entities include something not downstream")

    # --- clause 2: it says it is an estimate, and shows its working ------------
    if result["prevented"] and not result["summary"].startswith("Estimate."):
        failures.append(f"{where}: the summary does not present itself as an estimate")
    basis = " ".join(result["basis"])
    for phrase, why in (
        ("immediate and complete", "the efficacy assumption is not stated"),
        ("another route", "the adaptive-attacker assumption is not stated"),
    ):
        if phrase not in basis:
            failures.append(f"{where}: {why}")
    if not result["basis"]:
        failures.append(f"{where}: a number with no basis reads as a measurement")

    print(
        f"{where}: {len(result['prevented'])} pre-empted, "
        f"{len(result['unavoidable'])} unavoidable, "
        f"{round(result['gap_seconds'] / 60)} min gap, {len(result['basis'])} basis lines"
    )

    # --- clause 3: it refuses what the timeline cannot support -----------------
    too_early = (moment - timedelta(hours=1)).isoformat()
    try:
        counterfactual(api, incident_id, first["entity_key"], too_early)
    except urllib.error.HTTPError as exc:
        if exc.code != 422:
            failures.append(f"{where}: acting before the first record gave HTTP {exc.code}")
        else:
            print(f"{where}: refuses a moment before the first record, as it must")
    else:
        failures.append(
            f"{where}: answered what acting an hour before the first record of "
            "that entity would have saved. That question asks what we would have "
            "done knowing something nothing had observed."
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

        if "if we had acted sooner" not in lowered:
            failures.append(f"{incident_id}: the page shows no counterfactual panel")
        if "estimate" not in lowered:
            failures.append(f"{incident_id}: the page does not mark the number an estimate")

        for step in result["prevented"]:
            if step["entity_key"] not in body:
                failures.append(f"{incident_id}: {step['entity_key']} is not shown as pre-empted")
        # The half that keeps it honest has to be on screen too.
        for step in result["unavoidable"]:
            if step["entity_key"] not in body:
                failures.append(
                    f"{incident_id}: {step['entity_key']} would have happened anyway and "
                    "the page does not say so"
                )
        for phrase in ("immediate and complete", "another route"):
            if phrase not in lowered:
                failures.append(f"{incident_id}: the page omits the assumption {phrase!r}")

        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if overflow > 1:
            failures.append(f"{incident_id}: {overflow}px of horizontal overflow")
        print(f"{incident_id}: page shows the estimate, the remainder and the assumptions")
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
            "no stored incident has two timed causal steps, so nothing here measured "
            "anything. A green run in this state reports that R72 works because it "
            "was never exercised."
        )

    if not args.no_page:
        for incident_id, result in checked.items():
            check_page(args.site, incident_id, result, failures)

    if failures:
        print(f"\nFAIL ({len(failures)})")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"\nOK — {len(checked)} incident(s) estimated from records, caveated, and bounded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
