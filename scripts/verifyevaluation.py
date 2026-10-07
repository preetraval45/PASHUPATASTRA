"""Every number on /evaluation equals an independent recount (R125).

A page whose subject is the weakness of an evaluation is the single worst page
to get wrong, so this recomputes its figures from the corpus and the harness
without going through the generated manifest at all — a manifest checked
against itself proves only that a file is internally consistent.

It also checks three absences, which on this page carry more weight than the
numbers:

* an arm with no recorded runs says so, and does not render as a zero that
  could be read as a measured zero;
* the review's open findings appear on the page, in full, as open;
* no accuracy figure is shown while no model run exists behind it. A page
  claiming 0% diagnosis accuracy would be the invented metric this whole
  project is arranged against, and the failure mode of a page like this is to
  quietly become a scoreboard.

    python scripts/verifyevaluation.py [--site URL]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT))

from pashupatastra import diagnosis
from pashupatastra.pib import load_corpus

from benchmark.harness.inject import UNSUPPORTED
from benchmark.harness.run import ARM_NAMES

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

MANIFEST = ROOT / "apps" / "web" / "lib" / "evaluation.generated.json"
SITE = "https://pashupatastra.vercel.app"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=SITE)
    args = parser.parse_args()
    failures: list[str] = []

    if not MANIFEST.exists():
        print("FAIL  no manifest — run python scripts/buildevaluation.py")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    # Recounted from source, not read back from the manifest.
    corpus = load_corpus(str(ROOT / "benchmark" / "incidents" / "pib"))
    scoreable = diagnosis.scoreable(corpus)
    options = diagnosis.labels(corpus)

    expected = {
        "scenarios": len(corpus),
        "scoreable": len(scoreable),
        "options": len(options),
        "blocked": len(UNSUPPORTED),
        "arms": len(ARM_NAMES),
    }
    actual = {
        "scenarios": manifest["corpus"]["scenarios"],
        "scoreable": manifest["diagnosis"]["scoreable"],
        "options": manifest["diagnosis"]["options"],
        "blocked": len(manifest["injection"]["blocked"]),
        "arms": manifest["arms_declared"],
    }
    for key, want in expected.items():
        got = actual[key]
        mark = "ok " if got == want else "FAIL"
        print(f"  {mark} {key:12} manifest {got:4}   recount {want:4}")
        if got != want:
            failures.append(f"{key}: the page says {got}, a recount says {want}")

    # The claim the whole page rests on: one distinct label per scoreable
    # scenario, so the task really is a 60-way choice and the stated baseline
    # is the true one.
    if len(options) != len(scoreable):
        failures.append(
            f"{len(options)} labels for {len(scoreable)} scenarios — the stated "
            "baseline assumes one distinct label each"
        )

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 1400}).new_page()
        response = page.goto(f"{args.site}/evaluation", wait_until="networkidle")
        if response is None or response.status >= 400:
            print(f"FAIL  /evaluation answered {response.status if response else 'nothing'}")
            browser.close()
            return 1
        text = page.inner_text("main")

        for number in (len(corpus), len(scoreable), len(options)):
            if str(number) not in text:
                failures.append(f"{number} is a recounted figure and is not on the page")

        # Every arm is named, and one with no data says so rather than showing
        # a zero a reader could take for a measurement.
        for name in ARM_NAMES:
            arm = page.locator(f"[data-arm='{name}']")
            if arm.count() == 0:
                failures.append(f"arm '{name}' is declared by the harness and is not on the page")
                continue
            recorded = next((a for a in manifest["arms"] if a["name"] == name), None)
            if recorded and not recorded["records"] and "absent" not in arm.inner_text().lower():
                failures.append(f"arm '{name}' has no runs and does not say so")

        # The review, published rather than summarised.
        for finding in manifest["review"]["findings"]:
            marker = page.locator(f"[data-finding='{finding['key']}']")
            if marker.count() == 0:
                failures.append(f"review finding '{finding['key']}' is not on the page")
                continue
            shown = marker.inner_text()
            # A finding trimmed to its gentlest clause is the failure worth
            # catching: the sentence has to survive intact.
            if finding["finding"][:60] not in " ".join(shown.split()):
                failures.append(f"review finding '{finding['key']}' is not shown as written")
            if finding["status"] not in shown:
                failures.append(f"review finding '{finding['key']}' does not show its status")

        open_findings = [f for f in manifest["review"]["findings"] if f["status"] == "open"]
        print(f"\n  {len(manifest['review']['findings'])} findings published, {len(open_findings)} open")

        # No score while there is no run behind one.
        if manifest["diagnosis"]["measured"] is None:
            if manifest["diagnosis"]["absent"].split(".")[0][:40] not in text:
                failures.append("diagnosis is unmeasured and the page does not say why")
            for invented in ("0%", "0.0%"):
                if f"accuracy {invented}" in text.lower():
                    failures.append(f"an unmeasured accuracy renders as {invented}")

        browser.close()

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("every figure recounts, every arm without data says so, the review is published whole")
    return 0


if __name__ == "__main__":
    sys.exit(main())
