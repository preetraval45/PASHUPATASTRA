"""R68: the reasoning on screen is the reasoning that happened.

Three clauses, and the first two are checked against the API rather than against
the page, because a page is perfectly capable of rendering a convincing account
of steps nobody took. The answer is obtained from `/agent/chat` first; what the
browser shows then has to match it.

* **Every step names the records it read.** A `tool_result` in the trace must
  carry the refs its lookup returned, and every one of those refs must be a ref
  the answer could legitimately cite — not a plausible-looking id the renderer
  invented. A step that reports only `ok` leaves the screen narrating rather
  than citing.
* **A rejected reading names what rejected it.** Every entry the answer keeps in
  `considered` must name at least one ref, and those refs must resolve — the
  same standard citations are held to, because a rejection a reader cannot check
  spends their trust without earning it.
* **It is stored, not regenerated.** The same turn is read back out of the audit
  ledger and required to carry the same rejections. Re-asking a model gives a
  different trace; the ledger has to hold the one that produced this answer.

The question is chosen to have a real alternative: the credential-stuffing
scenario exists because "the user is travelling" is a reasonable reading until
the interval kills it. A question with no alternative would let an agent that
never fills the field pass.

Usage:  python scripts/verifytrace.py [--site URL] [--api URL]
"""

from __future__ import annotations

import argparse
import io
import json
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
INCIDENT = "INC-2026-0901"
QUESTION = "Was this really an attack, or could the user just be travelling?"

# A second question, on a second incident, whose answer is not in the evidence
# blocks and has to be fetched. Without it the first clause is never exercised:
# the travelling question is answered from the incident alone, and a run with no
# lookups in it cannot have checked that lookups name what they read.
LOOKUP_INCIDENT = "INC-2026-0903"
LOOKUP_QUESTION = "What is the blast radius of the busiest host here?"


def get(api: str, path: str):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(api + path, headers={"User-Agent": "verify"}), timeout=60
        )
    )


def ask(api: str, incident: str, question: str) -> dict | None:
    """One turn, retried past the free tier's per-minute allowance.

    A 429 is the deployment behaving correctly under a limit it documents, so
    waiting is right and reporting it as a defect would not be.

    A full window per attempt, not a fraction of one. The limit is tokens per
    minute and a retried turn spends tokens on every call that succeeds before
    the one that fails, so short backoffs re-burn the allowance as fast as it
    refills and five attempts get no further than one.
    """
    request = urllib.request.Request(
        api + "/agent/chat",
        data=json.dumps({"incident_id": incident, "message": question}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "verify"},
    )
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(request, timeout=180))
        except urllib.error.HTTPError as error:
            if error.code != 429:
                raise
            if attempt < 2:
                time.sleep(65)
    return None


def citable_refs(api: str, incident_id: str) -> set[str]:
    """Everything an answer about this incident is entitled to cite.

    Assembled from the store rather than read off the answer, so a trace that
    claims to have read something the store does not have is caught instead of
    being taken as its own evidence.
    """
    incident = get(api, f"/incidents/{incident_id}")
    citable = {incident_id}
    for index in range(len(incident["causal_chain"])):
        citable.add(f"{incident_id}#chain-{index}")
    for index in range(len(incident["hypotheses"])):
        citable.add(f"{incident_id}#hypothesis-{index}")
    for step in incident["plan"]:
        citable.add(f"{incident_id}#plan-{step['order']}")
    for link in incident["causal_chain"]:
        citable.update(link["evidence"])
    for hypothesis in incident["hypotheses"]:
        citable.update(hypothesis["evidence"])
        citable.update(hypothesis["contradicted_by"])
    return citable


def check_lookups(answer: dict, citable: set[str], where: str, failures: list[str]) -> int:
    """Every step names the records it read."""
    lookups = [step for step in answer["trace"] if step["kind"] == "tool_result"]
    for step in lookups:
        refs = (step.get("detail") or {}).get("refs")
        if refs is None:
            failures.append(f"{where}: {step['name']} read something and did not say what")
            continue
        for ref in refs:
            # An entity key is citable by construction — it is the thing the
            # lookup was for — so only the store-backed ids are checked here.
            if ":" not in ref and ref not in citable:
                failures.append(
                    f"{where}: {step['name']} claims to have read {ref!r}, which is not stored"
                )
    return len(lookups)


def check_answer(api: str, answer: dict, failures: list[str]) -> None:
    citable = citable_refs(api, INCIDENT)
    lookups = check_lookups(answer, citable, INCIDENT, failures)

    considered = answer.get("considered") or []
    if not considered:
        failures.append(
            "nothing was ruled out on the question this incident exists to pose — "
            "the alternative reading is in the evidence with what contradicts it"
        )
    for item in considered:
        if not item.get("ruled_out_by"):
            failures.append(f"{item['reading']!r} is listed as ruled out and names nothing")
        for ref in item.get("ruled_out_by", []):
            if ref not in citable:
                failures.append(f"{item['reading']!r} is ruled out by {ref!r}, which is not stored")

    print(
        f"api: {lookups} lookups, {len(considered)} rejections, "
        f"{len(answer.get('dropped_considered') or [])} dropped"
    )


def check_stored(api: str, answer: dict, failures: list[str]) -> None:
    """The ledger holds the reasoning, not a summary of it."""
    records = get(api, f"/audit?incident_ref={INCIDENT}&limit=20")
    turns = [record for record in records if record["kind"] == "agent_turn"]
    if not turns:
        failures.append("the turn was not written to the audit ledger at all")
        return
    detail = turns[0]["detail"]
    if [item["reading"] for item in detail.get("considered") or []] != [
        item["reading"] for item in answer.get("considered") or []
    ]:
        failures.append("the stored turn does not carry the rejections the answer returned")
    if not detail.get("trace"):
        failures.append("the stored turn carries no trace — it cannot be audited later")
    print(f"stored: {len(detail.get('trace') or [])} steps, "
          f"{len(detail.get('considered') or [])} rejections")


def check_page(site: str, answer: dict, failures: list[str]) -> None:
    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 1000})
        page.goto(f"{site}/incidents/{INCIDENT}", wait_until="networkidle", timeout=90_000)
        page.get_by_role("button", name="Ask about this incident").click()
        page.wait_for_timeout(400)
        page.locator("textarea").first.fill(QUESTION)
        page.get_by_role("button", name="Ask", exact=True).click()
        page.wait_for_selector("[data-turn='sati']", timeout=180_000)
        page.wait_for_timeout(800)

        panel = page.locator("[data-considered]")
        if not panel.count():
            failures.append("the answer ruled something out and the page does not show it")
        else:
            shown = " ".join(panel.first.inner_text().split()).lower()
            for item in answer.get("considered") or []:
                if item["reading"].lower()[:40] not in shown:
                    failures.append(f"the page omits the rejection {item['reading']!r}")
                for ref in item["ruled_out_by"]:
                    if ref.lower() not in shown:
                        failures.append(f"{item['reading']!r} is shown without its ref {ref}")
            # Every ref on that panel is a link, because the claim being made is
            # that a reader can go and check it.
            links = panel.first.locator("a").count()
            refs = sum(len(item["ruled_out_by"]) for item in answer.get("considered") or [])
            if links < refs:
                failures.append(f"{refs} refs shown as rejections, only {links} are links")

        trace = page.locator("[data-trace]")
        if not trace.count():
            failures.append("the steps are not on the page")
        else:
            trace.first.locator("summary").click()
            page.wait_for_timeout(300)
            body = " ".join(trace.first.inner_text().split())
            for step in answer["trace"]:
                for ref in (step.get("detail") or {}).get("refs") or []:
                    if ref.split("#")[-1] not in body:
                        failures.append(f"the trace on screen omits the record {ref}")

        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if overflow > 1:
            failures.append(f"{overflow}px of horizontal overflow with the trace open")
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--api", default=API)
    args = parser.parse_args()

    failures: list[str] = []
    answer = ask(args.api, INCIDENT, QUESTION)
    if answer is None:
        print("SKIP — the model allowance was exhausted; nothing was measured")
        return 1
    if not answer.get("grounded"):
        failures.append("the answer was ungrounded, so its reasoning is not worth checking")

    check_answer(args.api, answer, failures)
    check_stored(args.api, answer, failures)

    # The lookup clause, on a question that has to fetch something. Failing when
    # nothing was looked up is deliberate: a green run that never called a tool
    # has not checked the half of this task about naming records.
    probe = ask(args.api, LOOKUP_INCIDENT, LOOKUP_QUESTION)
    if probe is None:
        failures.append("the model allowance ran out before any lookup was measured")
    else:
        found = check_lookups(
            probe, citable_refs(args.api, LOOKUP_INCIDENT), LOOKUP_INCIDENT, failures
        )
        if found == 0:
            failures.append(
                f"{LOOKUP_QUESTION!r} was answered with no lookup, so nothing proved that "
                "a lookup names the records it read"
            )
        else:
            print(f"lookups: {found} on {LOOKUP_INCIDENT}, each naming what it read")

    check_page(args.site, answer, failures)

    if failures:
        print(f"FAIL ({len(failures)})")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("OK — every step names what it read, every rejection names what closed it, stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
