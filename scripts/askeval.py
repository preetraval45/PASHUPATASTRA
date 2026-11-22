"""Score Sati AI's answers against a pre-declared question set (benchmark/ask/*.yaml).

    python scripts/askeval.py --set dev                 # the live API
    python scripts/askeval.py --set test --local        # this checkout, PASHU_MODEL_PROVIDER=sati
    python scripts/askeval.py --set test --out docs/research/ask.md

Correct means the answer contains an accepted string at a word start (case-insensitive), or,
for a question marked decline, that it was declined. Anything else is wrong or abstained, and
both count against accuracy.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LIVE = "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"
ABSTAINED = re.compile(r"couldn't find|won't guess|what would you like to know|outside what", re.IGNORECASE)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def asker(local: bool, api: str):
    if not local:
        def ask(message: str) -> dict:
            body = json.dumps({"message": message}).encode()
            request = urllib.request.Request(f"{api}/agent/ask", data=body,
                                             headers={"content-type": "application/json"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        return ask
    os.environ["PASHU_MODEL_PROVIDER"] = "sati"
    sys.path[:0] = [str(ROOT / "services" / "api")]
    from fastapi.testclient import TestClient

    from app.main import app
    client = TestClient(app)

    def ask(message: str) -> dict:
        response = client.post("/api/v1/agent/ask", json={"message": message})
        response.raise_for_status()
        return response.json()
    return ask


def judge(item: dict, reply: dict) -> str:
    text = reply.get("answer", "")
    if item.get("decline"):
        return "correct" if reply.get("declined") else "wrong"
    if reply.get("declined") or ABSTAINED.search(text):
        return "abstained"
    hit = any(re.search(r"\b" + re.escape(a), text, re.IGNORECASE) for a in item["accept"])
    return "correct" if hit else "wrong"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="dev", choices=["dev", "test", "test2"])
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--api", default=LIVE)
    parser.add_argument("--out", help="write a markdown report here")
    parser.add_argument("--show", action="store_true", help="print every answer")
    args = parser.parse_args()

    items = yaml.safe_load((ROOT / "benchmark" / "ask" / f"{args.set}.yaml").read_text(encoding="utf-8"))["questions"]
    ask = asker(args.local, args.api)
    rows = []
    for item in items:
        started = time.perf_counter()
        try:
            reply = ask(item["q"])
            verdict = judge(item, reply)
        except Exception as error:  # an error is a failure, never skipped
            reply, verdict = {"answer": f"ERROR {error}"}, "error"
        seconds = time.perf_counter() - started
        rows.append({**item, "verdict": verdict, "seconds": round(seconds, 2),
                     "answer": reply.get("answer", ""), "area": reply.get("area")})
        mark = {"correct": "+", "wrong": "x", "abstained": "?", "error": "!"}[verdict]
        print(f"{mark} {seconds:5.1f}s {item['q']}", flush=True)
        if args.show or verdict != "correct":
            print("    " + reply.get("answer", "")[:300].replace("\n", " "), flush=True)

    lines = [f"# Sati AI answers ({args.set} set)", "",
             f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `scripts/askeval.py` against "
             f"{'this checkout' if args.local else args.api}. Do not edit by hand.", "",
             "| Topic | n | Correct | 95% CI | Wrong | Abstained | Error | Median s |", "|---|---|---|---|---|---|---|---|"]
    for topic in ("general", "security", "all"):
        subset = [r for r in rows if topic == "all" or r["topic"] == topic]
        n = len(subset)
        count = {v: sum(r["verdict"] == v for r in subset) for v in ("correct", "wrong", "abstained", "error")}
        low, high = wilson(count["correct"], n)
        times = sorted(r["seconds"] for r in subset)
        median = times[n // 2] if n else 0
        lines.append(f"| {topic} | {n} | {count['correct'] / max(1, n):.3f} | {low:.3f}–{high:.3f} | "
                     f"{count['wrong']} | {count['abstained']} | {count['error']} | {median:.1f} |")
    lines += ["", "## Not correct", ""]
    lines += [f"- **{r['verdict']}** — {r['q']} → {r['answer'][:160].replace(chr(10), ' ')}"
              for r in rows if r["verdict"] != "correct"]
    report = "\n".join(lines) + "\n"
    print("\n" + report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
