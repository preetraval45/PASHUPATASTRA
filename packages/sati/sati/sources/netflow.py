"""Labelled network flows: UNSW-NB15 and CIC-IDS2017.

Both datasets are read from local folders. On Kaggle these are the attached
datasets `mrwellsdavid/unsw-nb15` and `chethuhn/network-intrusion-dataset`
(CIC's "MachineLearningCVE" CSVs, one per capture). The official downloads sit
behind a SharePoint folder and a request form, which CI cannot fetch.

**Licences: research use** (datasheets.md). Models trained here publish metrics,
never weights.

UNSW-NB15 ships official training and testing files. Their names are swapped
in the release relative to the paper (Moustafa & Slay 2015: training 175,341
records, testing 82,332), so the training set is chosen by size, and the file
each split came from is recorded.

CIC-IDS2017's per-day files are kept by day. A by-day split puts attack
families from later days in the test set only: that is the point of the split.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

UNSW_DROP = ("id", "attack_cat", "label")
UNSW_CATEGORICAL = ("proto", "service", "state")
# TTL fields nearly identify UNSW-NB15's attacks: the testbed's attack traffic
# had characteristic TTLs. Measured with and without them (datasheets.md).
UNSW_TTL = ("sttl", "dttl", "ct_state_ttl")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def _find(folder: Path, pattern: str) -> list[Path]:
    found = sorted(folder.rglob(pattern))
    if not found:
        raise FileNotFoundError(f"no {pattern} under {folder}")
    return found


def unsw(folder: Path) -> dict:
    """`{"train": frame, "test": frame, "files": {...}}`, each frame with
    `family` (attack category, "Normal" for benign) and `label` (0/1)."""
    frames = {p.name: pd.read_csv(p, low_memory=False) for p in _find(folder, "UNSW_NB15_*-set.csv")}
    if len(frames) != 2:
        raise ValueError(f"expected the official training and testing files, found {sorted(frames)}")
    (test_name, test), (train_name, train) = sorted(frames.items(), key=lambda kv: len(kv[1]))
    for frame in (train, test):
        frame["family"] = frame["attack_cat"].fillna("Normal").astype(str).str.strip().replace("", "Normal")
    return {"train": train, "test": test, "files": {"train": train_name, "test": test_name}}


def unsw_features(train: pd.DataFrame, test: pd.DataFrame, drop_ttl: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Numeric features. Categorical columns are coded from the training set
    only; a value never seen in training becomes -1."""
    drop = set(UNSW_DROP) | {"family"} | (set(UNSW_TTL) if drop_ttl else set())
    columns = [c for c in train.columns if c not in drop]
    a, b = train[columns].copy(), test[columns].copy()
    for col in UNSW_CATEGORICAL:
        if col in columns:
            codes = {v: i for i, v in enumerate(sorted(a[col].astype(str).unique()))}
            a[col] = a[col].astype(str).map(codes).astype(float)
            b[col] = b[col].astype(str).map(codes).fillna(-1).astype(float)
    return a.astype(float), b.astype(float)


def _day(path: Path) -> str:
    return next((d for d in DAYS if path.name.lower().startswith(d.lower())), "")


def cic(folder: Path) -> pd.DataFrame:
    """Every flow with its `day`, `family` ("BENIGN" for benign) and `label`.
    Column names are stripped of the source's stray spaces. Infinite values,
    which the CSVs contain, become missing."""
    parts = []
    paths = sorted(_find(folder, "*.pcap_ISCX.csv"), key=lambda p: (DAYS.index(_day(p)) if _day(p) else 9, p.name))
    for path in paths:
        frame = pd.read_csv(path, encoding="latin-1", low_memory=False)
        frame.columns = [c.strip() for c in frame.columns]
        frame["day"] = _day(path)
        parts.append(frame)
    data = pd.concat(parts, ignore_index=True)
    data["family"] = data.pop("Label").astype(str).str.strip().str.replace("�", "-").str.replace("\x96", "-")
    data["label"] = (data["family"] != "BENIGN").astype(int)
    features = [c for c in data.columns if c not in ("day", "family", "label")]
    data[features] = data[features].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return data


def cic_features(data: pd.DataFrame) -> list[str]:
    return [c for c in data.columns if c not in ("day", "family", "label")]
