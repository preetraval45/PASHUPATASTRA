"""NAB — the Numenta Anomaly Benchmark (MIT), real series only.

Lavin & Ahmad, *Evaluating Real-time Anomaly Detection Algorithms — the Numenta
Anomaly Benchmark* (ICMLA 2015). 58 series; the 47 under `real*` are real
data — AWS CloudWatch server metrics, ad-exchange rates, traffic sensors,
Twitter mention volumes and machine failures with known causes. The artificial
ones are left out: they test whether a detector finds a planted step, not
whether it survives real data.

Labels are NAB's anomaly *windows* (`labels/combined_windows.json`), as
timestamps. Everything is fetched at a pinned commit so a later change to the
repository cannot silently change a reported number.

Known limits, reported beside every result: Wu & Keogh (2021) show several NAB
labels are trivial or questionable, and that some series are "run-to-failure".
"""

from __future__ import annotations

import io
import json
import os
import time
import urllib.request
from pathlib import Path

import pandas as pd

REPO = "numenta/NAB"
REAL_FAMILIES = ("realAWSCloudwatch", "realAdExchange", "realKnownCause", "realTraffic", "realTweets")


def revision() -> str:
    """NAB's current commit. Authenticated when a token is present: anonymous
    calls share one rate limit across every job on a CI runner's address, and
    the training run failed on it once."""
    request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/commits/master")
    if token := os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=60) as r:
        return json.load(r)["sha"]


def _fetch(path: str, cache: Path, rev: str) -> bytes:
    target = cache / rev / path
    if target.exists() and target.stat().st_size > 0:
        return target.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://raw.githubusercontent.com/{REPO}/{rev}/{path}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                body = r.read()
            target.write_bytes(body)
            return body
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def windows(cache: Path, rev: str) -> dict[str, list[tuple[str, str]]]:
    """`family/file.csv` → anomaly windows as (start, end) timestamps; real only."""
    raw = json.loads(_fetch("labels/combined_windows.json", cache, rev))
    return {k: [tuple(w) for w in v] for k, v in raw.items() if k.split("/")[0] in REAL_FAMILIES}


def series(name: str, cache: Path, rev: str) -> pd.DataFrame:
    """One series: `timestamp` (datetime) and `value`."""
    frame = pd.read_csv(io.BytesIO(_fetch(f"data/{name}", cache, rev)))
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame


def labelled_ranges(frame: pd.DataFrame, wins: list[tuple[str, str]]) -> list[tuple[int, int]]:
    """Windows as inclusive-exclusive index ranges, the form `evaluation.Series` uses."""
    ranges = []
    for start, end in wins:
        mask = (frame["timestamp"] >= pd.Timestamp(start)) & (frame["timestamp"] <= pd.Timestamp(end))
        idx = mask[mask].index
        if len(idx):
            ranges.append((int(idx[0]), int(idx[-1]) + 1))
    return ranges
