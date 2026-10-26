"""SMD, the Server Machine Dataset (MIT): 28 real servers × 38 metrics.

Su et al., *OmniAnomaly* (KDD 2019), github.com/NetManAIOps/OmniAnomaly. The
machines come from a large internet company, five weeks at one-minute
resolution. The authors split each machine's series in half: the first half is
`train`, which has **no labels** and is assumed mostly normal, and the second
half is `test`, which has a label per minute.

The machines form three groups (`machine-1-*`, `machine-2-*`, `machine-3-*`).
Holding out a whole group tests a detector on servers whose behaviour it has
not seen.

Fetched at a pinned commit through NAB's loader helpers, so a later change to
the repository cannot silently change a reported number.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np

from sati.sources.nab import _fetch, revision  # noqa: F401 — revision is re-exported for callers

REPO = "NetManAIOps/OmniAnomaly"
BASE = "ServerMachineDataset"
MACHINES = (
    *(f"machine-1-{i}" for i in range(1, 9)),
    *(f"machine-2-{i}" for i in range(1, 10)),
    *(f"machine-3-{i}" for i in range(1, 12)),
)


def group(machine: str) -> str:
    return machine.rsplit("-", 1)[0]


def _matrix(body: bytes) -> np.ndarray:
    return np.loadtxt(io.BytesIO(body), delimiter=",", dtype=float, ndmin=2)


def machine(name: str, cache: Path, rev: str) -> dict:
    """`train` (n × 38, unlabelled), `test` (m × 38) and `labels` (m,) for one machine."""
    train = _matrix(_fetch(f"{BASE}/train/{name}.txt", cache, rev, REPO))
    test = _matrix(_fetch(f"{BASE}/test/{name}.txt", cache, rev, REPO))
    labels = _matrix(_fetch(f"{BASE}/test_label/{name}.txt", cache, rev, REPO)).ravel().astype(int)
    if len(labels) != len(test):
        raise ValueError(f"{name}: {len(labels)} labels for {len(test)} test rows")
    return {"name": name, "group": group(name), "train": train, "test": test, "labels": labels}


def ranges(labels: np.ndarray) -> list[tuple[int, int]]:
    """Runs of 1s as inclusive-exclusive index ranges."""
    padded = np.concatenate([[0], labels.astype(int), [0]])
    edges = np.flatnonzero(np.diff(padded))
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2], strict=True)]
