"""R64: every point traces to a named thing, and the misses are named.

The board is checked against the **briefing's own** entity list, not against
anything this script believes about the scenario. An earlier checker in this
repository decided what the right answer was and then graded the site on it,
which measured the checker.

So: ask what a player may investigate, deliberately open only some of it, and
require the debrief to account for **all** of it — opened plus missed equals the
board, with no overlap. A debrief that listed only the decisive miss would pass a
weaker check and would let a player conclude they had covered everything else.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
SITE = "https://pashupatastra.vercel.app"
INCIDENTS = ["INC-2026-0901", "INC-2026-0902", "INC-2026-0903"]


def get(path: str):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(API + path, headers={"User-Agent": "verify"}), timeout=45
        )
    )


def post(path: str, body: dict):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(
                API + path,
                data=json.dumps(body).encode(),
                headers={"User-Agent": "verify", "Content-Type": "application/json"},
                method="POST",
            ),
            timeout=45,
        )
    )


def main() -> int:
    failures: list[str] = []

    for incident_id in INCIDENTS:
        briefing = get(f"/game/{incident_id}/briefing")
        board = set(briefing["entities"])
        # Open exactly one, so there is always something to miss.
        opened_one = sorted(board)[:1]

        verdict = post(
            f"/game/{incident_id}/answer",
            {
                "diagnosis_id": briefing["candidates"][0]["id"],
                "action_id": briefing["actions"][0]["id"],
                "investigated": opened_one,
                "player_id": "",
            },
        )

        debrief = verdict.get("debrief")
        if not debrief:
            failures.append(f"{incident_id}: no debrief in the result")
            continue

        opened = {row["entity_key"] for row in debrief["opened"]}
        missed = {row["entity_key"] for row in debrief["missed"]}
        if opened | missed != board:
            failures.append(
                f"{incident_id}: the board is {len(board)} entities but the debrief "
                f"accounts for {len(opened | missed)}"
            )
        if opened & missed:
            failures.append(f"{incident_id}: {opened & missed} is in both lists")
        if opened != set(opened_one):
            failures.append(f"{incident_id}: opened {opened}, expected {set(opened_one)}")

        # Every line traces to a named thing.
        for line in verdict["breakdown"]:
            named = (
                line.get("evidence")
                or line.get("contradicted_by")
                or line.get("chose_action")
                or line.get("on_entities")
            )
            if not named:
                failures.append(f"{incident_id}: '{line['name']}' names nothing it judged")

        decisive = [row for row in debrief["missed"] if row["decisive"]]
        print(
            f"  {incident_id}: board {len(board)}, opened {len(opened)}, "
            f"missed {len(missed)}, decisive misses {len(decisive)}"
        )

        # --- R102: the sentence and the board cannot disagree -----------------
        # Open exactly one *decisive* entity — found from the debrief above
        # rather than decided here — and require full investigation marks, a
        # score line naming it, and a board that marks it decisive under
        # "opened". If a second decisive entity exists, the line must name it
        # as *also* holding the evidence rather than as a miss.
        holders = sorted(
            row["entity_key"] for row in debrief["opened"] + debrief["missed"] if row["decisive"]
        )
        if not holders:
            failures.append(f"{incident_id}: no entity is decisive, nothing to check")
            continue
        second = post(
            f"/game/{incident_id}/answer",
            {
                "diagnosis_id": briefing["candidates"][0]["id"],
                "action_id": briefing["actions"][0]["id"],
                "investigated": holders[:1],
                "player_id": "",
            },
        )
        line = next(row for row in second["breakdown"] if row["name"] == "Investigation")
        opened_rows = {row["entity_key"]: row for row in second["debrief"]["opened"]}
        if line["points"] != line["of"]:
            failures.append(f"{incident_id}: opened {holders[0]} and scored {line['points']}")
        if f"on {holders[0]}" not in line["note"]:
            failures.append(f"{incident_id}: score line does not name {holders[0]}")
        if not opened_rows.get(holders[0], {}).get("decisive"):
            failures.append(f"{incident_id}: board does not mark {holders[0]} decisive")
        for other in holders[1:]:
            if "also on" not in line["note"] or other not in line["note"]:
                failures.append(f"{incident_id}: {other} also holds proof and the line hides it")
        print(f"  {incident_id}: decisive on {holders}; opened {holders[0]}: {line['note']}")

    # --- the misses reach the screen ---------------------------------------
    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
        page.goto(f"{SITE}/blue-team/INC-2026-0903", wait_until="networkidle")

        # Panel titles are uppercased by CSS and `inner_text` reports *rendered*
        # text, so a lowercase substring search never matches and this check
        # passed while measuring nothing. Read the headings and compare them
        # case-insensitively instead — the same mistake this repository already
        # made once, in `verifybuild.py`.
        def headings() -> list[str]:
            return [
                h.strip().lower()
                for h in page.evaluate(
                    "() => [...document.querySelectorAll('main section h2')]"
                    ".map(h => h.textContent)"
                )
            ]

        before = headings()
        if "what you looked at" in before:
            failures.append("the debrief is visible before an attempt was made")
        else:
            print(f"  before an attempt: {len(before)} panels, no debrief among them")

        # And it must appear *after* one, or the check above proves only that a
        # panel nobody renders is not rendered.
        page.locator("button:has-text('host:app-07')").first.click()
        page.wait_for_timeout(700)
        groups = page.evaluate(
            "() => [...new Set([...document.querySelectorAll('input[type=radio]')]"
            ".map(r => r.name))]"
        )
        for name in groups[:2]:
            page.locator(f"input[type=radio][name='{name}']").first.check()
        page.locator("button:has-text('Commit to this answer')").click()
        page.wait_for_timeout(3500)

        after = headings()
        if "what you looked at" not in after:
            failures.append(f"the debrief did not appear after an attempt: {after}")
        else:
            print(f"  after an attempt: {after}")
        browser.close()

    print()
    if failures:
        for failure in dict.fromkeys(failures):
            print(f"FAIL  {failure}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
