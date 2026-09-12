"""R94 and R103: Sati looks before it declines, still declines when it should,
and never shows prose it could not cite.

Two failures are possible here and they pull in opposite directions, so both are
measured or neither result means anything.

**Refusing to look.** The agent answered "I cannot tell from what I have" at hop
zero while holding two tools that would have answered. That is the bug.

**Answering anyway.** The obvious over-correction is an agent that stops saying
"I cannot tell" at all and starts guessing, which is far worse — the whole
console exists to be checkable. So the battery contains questions that are
genuinely unanswerable, and the agent is required to keep refusing those.

A pass needs both. A run where everything is answered is a regression, not a
success, and a checker that only asked answerable questions could not tell.

Rate-limited on purpose: the free tier allows 8,000 tokens a minute and a
four-hop conversation is not small.
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
PAUSE = 45

# The battery lives in one file and has two readers. `services/api/tests/
# testagentchat.py` replays each case's scripted model output through the real
# route, deterministically, in CI; this script asks the live model the same
# questions and holds it to the same `expect` block. The cases and what they
# guard are documented in the file itself.
BATTERY_PATH = Path(__file__).resolve().parents[1] / "services" / "api" / "tests" / "battery.json"
BATTERY = json.loads(BATTERY_PATH.read_text(encoding="utf-8"))["cases"]


def ask(incident: str, message: str, attempts: int = 4) -> dict:
    """One question, with backoff on the free tier's rate limit.

    A 429 is not a result. Reporting "no tool was called" because the request
    never reached the model would be a checker inventing a finding, which is the
    failure this whole script exists to catch in something else.
    """
    body = json.dumps({"incident_id": incident, "message": message}).encode()
    request = urllib.request.Request(
        f"{API}/agent/chat",
        data=body,
        headers={"User-Agent": "pashupatastra-verify", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == attempts - 1:
                raise
            wait = 45 * (attempt + 1)
            print(f"   rate limited ({error.code}); waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def tool_hops(answer: dict) -> list[str]:
    """Which tools were actually called, from the trace the gateway records."""
    used = []
    for entry in answer.get("trace") or []:
        if entry.get("kind") in ("tool", "tool_call", "tools"):
            detail = entry.get("detail") or {}
            used.append(str(detail.get("name") or detail.get("tool") or entry.get("kind")))
    return used


def check(answer: dict, expect: dict, used: list[str]) -> list[str]:
    """The `expect` block, applied to a live reply. Mirrors the checker in
    `testagentchat.py` — kept in step by hand, because the two run in different
    processes and a shared module would have to live in one of them."""
    problems: list[str] = []
    proposed = expect.get("proposed_action", "any")
    got = answer.get("proposed_action_id")
    if proposed is None and got:
        problems.append(f"proposed {got}; must propose nothing")
    elif isinstance(proposed, str) and proposed.startswith("not:") and got == proposed[4:]:
        problems.append(f"proposed {got} on an incident that cannot take it")
    elif (
        isinstance(proposed, str)
        and proposed != "any"
        and not proposed.startswith("not:")
        and got != proposed
    ):
        problems.append(f"expected a proposal of {proposed}, got {got}")
    if expect.get("honest"):
        answerable = answer.get("answerable", True)
        if answerable and not answer.get("evidence_refs") and not answer.get("withheld"):
            problems.append("answerable prose reached the visitor with nothing cited")
    wanted = expect.get("answerable")
    if wanted is not None and bool(answer.get("answerable", True)) != wanted:
        if wanted:
            problems.append("declined a question its tools cover")
        else:
            problems.append(
                "ANSWERED a question nothing stored can answer — the over-correction, "
                "and worse than the bug"
            )
    if expect.get("tool") is True and not used:
        problems.append("no tool called for a question tools cover")
    if expect.get("tool") is False and used:
        problems.append(f"called {used} on a question nothing stored can answer")
    return problems


def main() -> int:
    failures: list[str] = []

    for index, case in enumerate(BATTERY):
        if index:
            time.sleep(PAUSE)
        question = case["question"]
        try:
            answer = ask(case["incident"], question)
        except urllib.error.HTTPError as error:
            failures.append(f"{case['id']}: HTTP {error.code}")
            continue

        used = tool_hops(answer)
        print(f"\n[{case['id']}] {question[:70]}")
        print(f"   tools called: {used or 'none'}")
        print(
            f"   answerable={answer.get('answerable', True)}  grounded={answer.get('grounded')}  "
            f"withheld={answer.get('withheld', False)}  cached={answer.get('cached', False)}  "
            f"proposed={answer.get('proposed_action_id')}"
        )
        print(f"   {(answer.get('answer') or '')[:150]}")
        for problem in check(answer, case["expect"], used):
            failures.append(f"{case['id']}: {problem}")

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("looks things up when it can, declines when it cannot, and shows nothing it did not cite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
