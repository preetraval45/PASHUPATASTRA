"""RCAEval — real fault-injection cases on three microservice systems.

Pham et al., *RCAEval: A Benchmark for Root Cause Analysis of Microservice
Systems* (WWW 2025). 735 cases on Online Boutique, Sock Shop and Train Ticket,
each with a labelled root-cause service, fault type, injection time and the
metrics the system emitted around it. Read from the Hugging Face copy (MIT),
which stores each case as Parquet and can be fetched one case at a time.

The revision is pinned per run: `revision()` resolves the dataset's current
commit once, every file is fetched at that commit, and results record it — so a
later upload to the dataset cannot silently change a number already reported.
"""

from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

REPO = "phamquiluan/RCAEval"
API = f"https://huggingface.co/api/datasets/{REPO}"


def revision() -> str:
    """The dataset's current commit, to pin every download in this run to."""
    with urllib.request.urlopen(API, timeout=60) as response:
        return json.load(response)["sha"]


def _url(path: str, rev: str) -> str:
    return f"https://huggingface.co/datasets/{REPO}/resolve/{rev}/{path}"


def fetch(path: str, cache: Path, rev: str, attempts: int = 4) -> Path:
    """One file, cached under the revision. Written atomically, so an
    interrupted download is never mistaken for a cached one."""
    target = cache / rev / path
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(_url(path, rev), timeout=120) as response:
                partial.write_bytes(response.read())
            partial.replace(target)
            return target
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def cases(cache: Path, rev: str) -> pd.DataFrame:
    """The case index: one row per case with its labels and shape."""
    return pd.read_parquet(fetch("cases.parquet", cache, rev))


def metrics(case: str, cache: Path, rev: str) -> pd.DataFrame:
    """One case's metrics: a `time` column (unix seconds) and one column per
    `<service>_<metric>`."""
    return pd.read_parquet(fetch(f"{case}/metrics.parquet", cache, rev))


def prefetch(names: list[str], cache: Path, rev: str, workers: int = 8) -> None:
    """Download many cases in parallel; idempotent."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda name: fetch(f"{name}/metrics.parquet", cache, rev), names))
