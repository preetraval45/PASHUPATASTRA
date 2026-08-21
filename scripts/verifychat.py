"""Drive the chat panel the way a visitor does, and check what comes back.

This is the half of R19–R21 that unit tests cannot cover. `testagentchat.py`
asserts our own behaviour against a scripted provider, which is where questions
with one right answer belong. Whether a *real* model, given real evidence,
produces an answer whose citations resolve is not that kind of question — it can
only be found out by asking.

    python scripts/verifychat.py --base http://localhost:3111

Checks, per starter question:

- the panel renders an answer at all
- the API marked it grounded
- every rendered citation is a link whose target exists on the page or resolves
  over HTTP — a citation that 404s is worse than one that is plainly unlinked,
  because it looks checkable and then is not
- no unresolved citations were dropped
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import unquote, urljoin

STARTERS = [
    "What happened?",
    "How do we know — what is the evidence?",
    "What is the blast radius?",
    "What should we do first?",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:3111")
    parser.add_argument("--incident", default="INC-2026-0901")
    parser.add_argument("--timeout", type=int, default=120_000)
    parser.add_argument("--pace", type=int, default=45_000,
                        help="ms to wait between questions, to stay under the "
                             "provider's per-minute token allowance")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed: pip install playwright && playwright install chromium")
        return 2

    url = f"{args.base}/incidents/{args.incident}"
    failures: list[str] = []
    seen_answers: dict[str, str] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="networkidle")

        panel = page.get_by_role("button", name="Ask about this incident")
        if not panel.count():
            print("FAIL: the chat panel is not on the incident page")
            return 1
        panel.click()
        print(f"{args.incident} — the panel opens\n")

        for index, question in enumerate(STARTERS):
            if index == 0:
                page.get_by_role("button", name=question, exact=True).click()
            else:
                # Paced under the free tier's per-minute token allowance. Fired
                # back to back, the later questions come back as rate limits and
                # the run reports a broken panel instead of a busy one.
                page.wait_for_timeout(args.pace)
                # Only the first turn shows the chips; the rest go through the
                # box, which is also the path a visitor takes for anything of
                # their own.
                box = page.get_by_label(f"Your question about {args.incident}")
                box.fill(question)
                box.press("Enter")

            try:
                page.wait_for_selector("text=Reading the evidence…", timeout=5_000)
            except Exception:
                pass
            page.wait_for_selector("text=Reading the evidence…", state="detached",
                                   timeout=args.timeout)

            # Located by data attribute, not by position. An earlier version
            # counted `<p>` elements and read the visitor's own question back as
            # though it were the reply — passing while testing nothing.
            turns = page.locator("[data-turn='sati']")
            if not turns.count():
                error = page.locator("[data-turn='error']")
                detail = error.last.inner_text() if error.count() else "no reply rendered"
                failures.append(f"{question}: {detail}")
                print(f"  x {question}\n      {detail}\n")
                continue

            turn = turns.nth(turns.count() - 1)
            body = turn.locator("[data-answer]").inner_text().strip()
            if not body:
                failures.append(f"{question}: empty answer")
                print(f"  x {question}\n      empty answer\n")
                continue

            flags = turn.get_by_text("not grounded").count()
            dropped = turn.get_by_text("unresolved citation").count()
            hrefs = [a.get_attribute("href") or "" for a in turn.locator("a").all()]

            bad = []
            for href in hrefs:
                if href.startswith("#"):
                    target = unquote(href[1:])
                    # Matched by attribute rather than by CSS id selector: these
                    # ids contain colons and plus signs from ISO timestamps,
                    # which a selector would read as syntax.
                    if not page.locator(f'[id="{target}"]').count():
                        bad.append(f"{href} → no such anchor")
                else:
                    response = page.request.get(urljoin(args.base, href))
                    if response.status >= 400:
                        bad.append(f"{href} → HTTP {response.status}")

            # Four questions that return one answer would pass every other
            # check here while proving nothing, so identical replies are a
            # failure rather than a curiosity.
            duplicate = next((q for q, a in seen_answers.items() if a == body), None)
            seen_answers[question] = body

            ok = not bad and not flags and not dropped and duplicate is None
            print(f"  {'ok' if ok else 'x '} {question}")
            print(f"      {body[:150]}")
            print(f"      {len(hrefs)} citations, all resolving" if not bad
                  else "      " + "; ".join(bad))
            if duplicate:
                print(f"      IDENTICAL to the answer for {duplicate!r}")
            if flags:
                print("      marked NOT GROUNDED")
            if dropped:
                print("      citations were dropped as unresolvable")
            print()

            if bad:
                failures.append(f"{question}: {'; '.join(bad)}")
            if flags:
                failures.append(f"{question}: not grounded")
            if dropped:
                failures.append(f"{question}: dropped citations")
            if duplicate:
                failures.append(f"{question}: identical answer to {duplicate!r}")

        browser.close()

    if failures:
        print(f"{len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("all four starter questions answered, grounded, every citation resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
