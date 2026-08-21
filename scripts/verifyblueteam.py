"""Play every scenario through the browser, and check the marking is real.

R27's criterion is that all three are playable start to finish and scored, and
that is not what the API tests establish: they prove the engine marks correctly,
not that a person can reach the marking through the interface.

**This checker does not know the answers, and must not.** The whole design keeps
them on the server, so a verifier holding a copy would be asserting against a
second source of truth that can drift. An earlier version guessed — it picked
the last option and called that "careful" — and reported two scenarios broken
because its guess happened to be the decoy. It was measuring itself.

What can be established without knowing anything:

- every candidate explanation can be submitted, and **exactly one** of them
  scores the diagnosis marks. That is what "the diagnosis is scored" means, and
  it is checkable from outside.
- holding the answers fixed and changing only whether the evidence was opened
  changes the investigation marks. That isolates one dimension.
- the reveal, the chain and the explanation of the wrong answer all appear.

    python scripts/verifyblueteam.py https://pashupatastra.vercel.app
"""

from __future__ import annotations

import argparse
import re
import sys

TOTAL = re.compile(r"(\d{1,3})\s*\n?\s*out of 100")
PART = re.compile(r"(Diagnosis|Response|Investigation)\s*\n?\s*(\d+)/(\d+)")


def attempt(page, base: str, scenario: str, *, diagnosis: int, investigate: bool) -> dict:
    """One attempt: pick the nth explanation, a fixed response, and either open
    every entity or none."""
    page.goto(f"{base}/blue-team/{scenario}", wait_until="networkidle")
    page.wait_for_timeout(500)

    opened = 0
    if investigate:
        for _ in range(12):
            buttons = page.get_by_role("button", name="look at this")
            if not buttons.count():
                break
            buttons.first.click()
            page.wait_for_timeout(350)
            opened += 1

    radios = page.locator("input[type=radio]")
    groups: dict[str, list] = {}
    for index in range(radios.count()):
        node = radios.nth(index)
        groups.setdefault(node.get_attribute("name") or "", []).append(node)

    groups["diagnosis"][diagnosis].check()
    # The same response every time, so the only thing moving between attempts is
    # what is being measured.
    groups["action"][len(groups["action"]) // 2].check()

    page.get_by_role("button", name="Commit to this answer").click()
    page.wait_for_selector("section:has-text('Marked')", timeout=60_000)
    page.wait_for_timeout(350)

    marked = page.locator("section:has-text('Marked')").first.inner_text()
    parts = {name: (int(got), int(of)) for name, got, of in PART.findall(marked)}
    return {
        "choices": len(groups["diagnosis"]),
        "opened": opened,
        "total": int(TOTAL.search(marked).group(1)),
        "parts": parts,
        "revealed": page.locator("section:has-text('What actually happened')").count() > 0,
        "decoy": page.locator("section:has-text('The plausible wrong answer')").count() > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", default="https://pashupatastra.vercel.app")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed")
        return 2

    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})

        page.goto(f"{args.base}/blue-team", wait_until="networkidle")
        page.wait_for_timeout(500)
        links = page.locator("a[href^='/blue-team/']")
        scenarios = [
            (links.nth(i).get_attribute("href") or "").rsplit("/", 1)[-1]
            for i in range(links.count())
        ]
        scenarios = [s for s in dict.fromkeys(scenarios) if s]
        print(f"{len(scenarios)} scenario(s) listed\n")
        if not scenarios:
            print("FAIL: no scenarios on the index")
            return 1

        for scenario in scenarios:
            first = attempt(page, args.base, scenario, diagnosis=0, investigate=True)
            runs = [first] + [
                attempt(page, args.base, scenario, diagnosis=n, investigate=True)
                for n in range(1, first["choices"])
            ]
            scored = [r for r in runs if r["parts"].get("Diagnosis", (0, 0))[0] > 0]

            # Same choices, nothing opened. Only the investigation marks should move.
            blind = attempt(page, args.base, scenario, diagnosis=0, investigate=False)

            problems = []
            if len(scored) != 1:
                problems.append(
                    f"{len(scored)} of {len(runs)} explanations scored the "
                    "diagnosis marks; exactly one should"
                )
            if not first["revealed"]:
                problems.append("no reveal after marking")
            if not first["decoy"]:
                problems.append("the wrong answer was never explained")

            looked = first["parts"].get("Investigation", (0, 0))[0]
            unlooked = blind["parts"].get("Investigation", (0, 0))[0]
            if not looked > unlooked:
                problems.append(
                    f"opening the evidence changed nothing "
                    f"({looked} vs {unlooked} investigation marks)"
                )

            ok = not problems
            print(f"  {'ok' if ok else 'x '} {scenario}")
            print(
                f"      {len(runs)} explanations tried, "
                f"{len(scored)} scored — totals {[r['total'] for r in runs]}"
            )
            print(
                f"      investigation: {looked} after opening {first['opened']} "
                f"entities, {unlooked} after opening none"
            )
            print(f"      reveal: chain {first['revealed']}, wrong answer explained {first['decoy']}")
            for problem in problems:
                print(f"      {problem}")
                failures.append(f"{scenario}: {problem}")
            print()

        browser.close()

    if failures:
        print(f"{len(failures)} problem(s)")
        return 1
    print("every scenario is playable start to finish, and the marking discriminates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
