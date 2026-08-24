"""R94: Sati looks before it declines — and still declines when it should.

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

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

API = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
PAUSE = 45

# (incident, question, must_use_a_tool, must_stay_answerable)
#
# `must_stay_answerable` is set from what the store actually holds, checked by
# hand against `/incidents/INC-2026-0903` — not from what the question sounds
# like it deserves. The first draft of this battery demanded an answer to "which
# hosts did ws-0148 open SMB to", and the stored chain says only "two hosts
# never previously contacted". Two other hosts appear in `affected_entities`,
# so the answer is *inferable* and nowhere *stated*, and asserting it is exactly
# the plausible-and-unverifiable claim the console refuses to make. Requiring the
# agent to make it would have been the checker deciding the answer.
BATTERY = [
    (
        "INC-2026-0903",
        "Which hosts did ws-0148 open SMB to, and what is the blast radius of the busiest one?",
        True,
        # Look, yes. Assert which two, no — the evidence does not say.
        False,
    ),
    (
        "INC-2026-0903",
        "What is the blast radius of app-07, and how many users does it touch?",
        True,
        True,
    ),
    (
        "INC-2026-0901",
        "How many users does the sso-portal asset reach if this spreads?",
        True,
        True,
    ),
    # The guard. Nothing stored answers this, and no tool reaches it, so the
    # correct behaviour is still to decline.
    (
        "INC-2026-0903",
        "What is the attacker's real name and which country do they live in?",
        False,
        False,
    ),
]


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


def main() -> int:
    failures: list[str] = []

    for index, (incident, question, needs_tool, should_answer) in enumerate(BATTERY):
        if index:
            time.sleep(PAUSE)
        try:
            answer = ask(incident, question)
        except urllib.error.HTTPError as error:
            failures.append(f"{question[:44]}… HTTP {error.code}")
            continue

        used = tool_hops(answer)
        answerable = answer.get("answerable", True)
        cached = answer.get("cached", False)
        print(f"\nQ: {question[:70]}")
        print(f"   tools called: {used or 'none'}")
        print(f"   answerable={answerable}  grounded={answer.get('grounded')}  cached={cached}")
        print(f"   {(answer.get('answer') or '')[:150]}")

        if needs_tool and not used:
            failures.append(
                f"no tool called for a question tools cover: {question[:50]}…"
            )
        if should_answer and not answerable:
            failures.append(f"declined a question its tools cover: {question[:50]}…")
        if not should_answer and answerable:
            failures.append(
                f"ANSWERED a question nothing stored can answer — this is the "
                f"over-correction, and it is worse than the bug: {question[:50]}…"
            )

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("looks things up when it can, and still declines when it cannot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
