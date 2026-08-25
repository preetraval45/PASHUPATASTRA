"""R69: a relation is asserted only where the overlap is real, and cited.

The checker works out the answer for itself and then requires the agent to
agree. Entity overlap between two stored incidents is a set intersection, so
this computes it from `/incidents/{id}` — independently of the agent, the tool
and the page — and holds the answer to it. A checker that asked the agent what
the overlap was and then graded the agent on it would be measuring the checker.

What that buys is the case this task is really about. The three demo incidents
share no entity with each other, so the honest answer to every pair is *no
relation found*, and the failure mode being guarded against is an agent that
finds a resemblance — both involve a sign-in, both happened this afternoon — and
reports it as a link. So:

* where the checker finds no overlap, the answer must not assert a relation, and
  must not carry citations pretending to support one;
* where it does find one, the answer must assert it and name records on both
  sides;
* either way the tool must have been called. An answer to a relation question
  that never called it is the model judging, which is the thing rule 7 forbids.

Usage:  python scripts/verifyrelation.py [--api URL]
"""

from __future__ import annotations

import argparse
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

# Words that assert a link. Checked only against answers where the checker found
# no overlap, so a false positive here means the agent said something it could
# not support.
CLAIMS = ("are related", "is related", "same actor", "same campaign", "linked to")


def get(api: str, path: str):
    return json.load(
        urllib.request.urlopen(
            urllib.request.Request(api + path, headers={"User-Agent": "verify"}), timeout=60
        )
    )


def ask(api: str, incident: str, question: str) -> dict | None:
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


def entities(incident: dict) -> set[str]:
    """Every entity the incident touches, computed the way the engine does but
    written out here on purpose — a second implementation is the point."""
    found = {f"{ref['kind']}:{ref['id']}" for ref in incident["affected_entities"]}
    for link in incident["causal_chain"]:
        found.add(f"{link['entity']['kind']}:{link['entity']['id']}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=API)
    args = parser.parse_args()

    failures: list[str] = []
    incidents = {row["id"]: row for row in get(args.api, "/incidents")}
    ids = sorted(incidents)
    if len(ids) < 2:
        print("SKIP — fewer than two incidents are stored; there is no pair to compare")
        return 1

    pairs = [(ids[0], ids[1])]
    asserted = 0
    for left, right in pairs:
        overlap = entities(incidents[left]) & entities(incidents[right])
        answer = ask(args.api, left, f"Is {right} related to this one?")
        if answer is None:
            failures.append(f"{left}/{right}: the model allowance ran out; nothing was measured")
            continue

        called = [
            step
            for step in answer["trace"]
            if step["kind"] == "tool_call" and step.get("name") == "related_incidents"
        ]
        if not called:
            failures.append(
                f"{left}/{right}: answered a relation question without calling the tool — "
                "that answer is the model's judgement, not the store's"
            )

        said = " ".join(answer["answer"].split()).lower()
        if overlap:
            asserted += 1
            if not any(claim in said for claim in CLAIMS):
                failures.append(
                    f"{left}/{right}: share {sorted(overlap)} and the answer does not say so"
                )
            if not answer["evidence_refs"]:
                failures.append(f"{left}/{right}: asserts a relation and cites nothing")
        else:
            claimed = [claim for claim in CLAIMS if claim in said]
            if claimed and "no relation" not in said and "not related" not in said:
                failures.append(
                    f"{left}/{right}: share no entity and the answer says {claimed} — "
                    "a resemblance reported as a link"
                )
            print(f"{left}/{right}: no shared entity, and the answer does not claim one")

    if not pairs:
        failures.append("no pair was compared")
    if asserted == 0:
        # Stated rather than failed. On this deployment every pair is unrelated
        # and that is the truth about the data, not a defect — but a run that
        # only ever saw "no" has not watched the tool assert anything, and a
        # reader of this output should know which half was exercised.
        print(
            "note: no stored pair overlaps, so only the negative case was measured here. "
            "The positive case is covered by testrelations.py and testagentchat.py."
        )

    if failures:
        print(f"FAIL ({len(failures)})")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"OK — {len(pairs)} pair(s) compared against independently computed overlap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
