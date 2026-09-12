"""R71: a drafted rule parses as Sigma, every field says where it came from, and
what the telemetry could not supply is stated in the rule rather than beside it.

Three clauses, and each is checked against something other than the thing that
produced it:

- **Parses as Sigma** — by pySigma, the reference parser the detection ecosystem
  actually uses, not by our own `sigma.validate`. Our validator is the same
  author marking their own work: it would accept a rule wrong in exactly the way
  we misread the specification.
- **Names its source field** — and the field is resolved against the event it
  cites. "Every mapping has a source_field" is satisfied by a mapping claiming
  `payload.principal` for a value that is not in `payload.principal`, which is
  the near-miss citation R59 is about, one layer further in. So the event is
  fetched and the claimed field is read.
- **States its uncertainty in the output** — checked in the YAML text, because
  the YAML is what gets copied into a detection repository and the panel that
  explained the limitations does not travel with it.

The page half then requires the browser to show the same mapping table the API
returned, so a screen rendering a convincing rule nobody drafted fails.

Usage:  python scripts/verifysigma.py [--site URL] [--api URL] [--no-page]
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


def source_value(event: dict, source_field: str) -> str | None:
    """Read the field a mapping claims it came from.

    Deliberately a lookup rather than a substring search over the whole event.
    A value that appears *somewhere* in the record proves nothing about the
    field it was attributed to, and attributing `ws-0148` to
    `payload.source_address` when it came from the entity key is exactly the
    kind of mapping that looks checkable and is not.
    """
    if source_field == "entity_ref.id":
        key = str(event.get("entity_key") or "")
        return key.split(":", 1)[1] if ":" in key else None
    if source_field.startswith("payload."):
        payload = event.get("payload") or {}
        value = payload.get(source_field.split(".", 1)[1])
        return None if value is None else str(value)
    if source_field.startswith("labels."):
        labels = event.get("labels") or {}
        value = labels.get(source_field.split(".", 1)[1])
        return None if value is None else str(value)
    return None


def check_rule(api: str, incident_id: str, rule: dict, failures: list[str]) -> None:
    where = f"{incident_id}/{rule['technique']['id'] if rule.get('technique') else '?'}"
    text = rule["yaml"]

    # --- clause 1: it parses, by somebody else's parser ------------------------
    try:
        from sigma.rule import SigmaRule
    except ImportError:
        failures.append(
            "pysigma is not installed, so the clause about parsing as valid Sigma "
            "cannot be measured. pip install pysigma"
        )
    else:
        try:
            parsed = SigmaRule.from_yaml(text)
            if parsed.errors:
                failures.append(f"{where}: pysigma reports {parsed.errors}")
            elif parsed.title != rule["title"]:
                failures.append(
                    f"{where}: the parsed title {parsed.title!r} is not the one the API "
                    f"reported ({rule['title']!r})"
                )
        except Exception as exc:  # noqa: BLE001 - any parse failure is the finding
            failures.append(f"{where}: pysigma refused the rule — {type(exc).__name__}: {exc}")

    if rule.get("valid") is not True:
        failures.append(f"{where}: the API reports its own output invalid — {rule['problems']}")

    # --- clause 2: every field names where it came from, and it is there -------
    if not rule["mappings"]:
        failures.append(f"{where}: a rule was served with no mapped field")
    for mapping in rule["mappings"]:
        field = mapping["sigma_field"]
        if not mapping["source_field"]:
            failures.append(f"{where}: {field} names no source field")
            continue
        if not mapping["refs"]:
            failures.append(f"{where}: {field} cites nothing")
            continue

        found = False
        for ref in mapping["refs"]:
            try:
                event = get(api, f"/events/{urllib.parse.quote(ref, safe='')}")
            except urllib.error.HTTPError:
                failures.append(f"{where}: {field} cites {ref}, which resolves to nothing")
                continue
            actual = source_value(event, mapping["source_field"])
            if actual is not None and str(mapping["value"]) in actual:
                found = True
        if not found:
            failures.append(
                f"{where}: {field}={mapping['value']!r} claims to come from "
                f"{mapping['source_field']} on {mapping['refs']}, and that field does "
                "not carry it"
            )

    # --- clause 3: the uncertainty is inside the document ----------------------
    if "DRAFT" not in text:
        failures.append(f"{where}: the rule does not say it is a draft")
    if "x-provenance" not in text:
        failures.append(
            f"{where}: the mapping table is not in the rule, so a reviewer who pasted "
            "it into a repository could not tell where any field came from"
        )
    if rule["gaps"] and "x-gaps" not in text:
        failures.append(
            f"{where}: {len(rule['gaps'])} gaps are reported by the API and none is in "
            "the document that travels"
        )
    if rule["behavioural"] is False and "WARNING" not in text:
        failures.append(
            f"{where}: every field is an instance value and the rule does not say so — "
            "it presents an indicator match as a detection for the technique"
        )
    if "status: experimental" not in text:
        failures.append(f"{where}: the rule claims a status above experimental")

    fields = ", ".join(m["sigma_field"] for m in rule["mappings"])
    print(
        f"{where}: {len(rule['mappings'])} fields ({fields}), {len(rule['gaps'])} gaps, "
        f"{'generalises' if rule['behavioural'] else 'indicator match'} — parses"
    )


def check_api(api: str, failures: list[str]) -> dict:
    incidents = get(api, "/incidents")
    drafted: dict[str, dict] = {}
    considered = 0

    for incident in incidents:
        incident_id = incident["id"]
        index = get(api, f"/incidents/{incident_id}/detection-rule")
        for technique in index["techniques"]:
            considered += 1
            url = (
                f"/incidents/{incident_id}/detection-rule/"
                f"{urllib.parse.quote(technique['id'], safe='')}"
            )
            try:
                rule = get(api, url)
            except urllib.error.HTTPError as exc:
                if exc.code == 422:
                    # A refusal is a correct answer about the data, not a failure.
                    # It is printed so a green run cannot hide that a step was
                    # declined rather than drafted.
                    print(f"{incident_id}/{technique['id']}: refused — {exc.read().decode()[:120]}")
                    continue
                failures.append(f"{incident_id}/{technique['id']}: HTTP {exc.code}")
                continue
            check_rule(api, incident_id, rule, failures)
            drafted.setdefault(incident_id, rule)

    if not considered:
        failures.append(
            "no stored incident carries an attack technique, so nothing here measured "
            "anything. A green run in this state would be reporting that R71 works "
            "because it was never exercised."
        )
    if considered and not drafted:
        failures.append(
            f"{considered} techniques were offered and every one was refused, so no rule "
            "was checked end to end"
        )
    return drafted


def check_page(site: str, drafted: dict, failures: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 1200})
        for incident_id, rule in drafted.items():
            page.goto(
                f"{site}/incidents/{incident_id}", wait_until="networkidle", timeout=90_000
            )
            page.wait_for_timeout(600)
            body = " ".join(page.locator("main").inner_text().split())

            if rule["title"] not in body:
                failures.append(f"{incident_id}: the page does not show {rule['title']!r}")

            # The mapping table is the clause. A page showing the rule and not
            # where its fields came from is the impressive half without the
            # checkable one.
            for mapping in rule["mappings"]:
                if mapping["sigma_field"] not in body:
                    failures.append(f"{incident_id}: {mapping['sigma_field']} is not on the page")
                if mapping["source_field"] not in body:
                    failures.append(
                        f"{incident_id}: the page shows {mapping['sigma_field']} without "
                        f"{mapping['source_field']}, the field it was read from"
                    )
            for gap in rule["gaps"]:
                if gap["sigma_field"] not in body:
                    failures.append(f"{incident_id}: gap {gap['sigma_field']} is not shown")

            if rule["behavioural"] is False and "indicator match" not in body.lower():
                failures.append(
                    f"{incident_id}: the page does not mark this an indicator match"
                )

            overflow = page.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            if overflow > 1:
                failures.append(f"{incident_id}: {overflow}px of horizontal overflow")
            print(f"{incident_id}: page shows the rule, its mapping table and its gaps")
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    parser.add_argument(
        "--no-page",
        action="store_true",
        help="Check the API only. The page half needs playwright and a running site.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    drafted = check_api(args.api, failures)
    if not args.no_page and drafted:
        check_page(args.site, drafted, failures)

    if failures:
        print(f"\nFAIL ({len(failures)})")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"\nOK — {len(drafted)} incidents drafted a rule that parses, cites and caveats")
    return 0


if __name__ == "__main__":
    sys.exit(main())
