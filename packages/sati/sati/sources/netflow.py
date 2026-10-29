"""Labelled network flows: UNSW-NB15, CIC-IDS2017 and NSL-KDD.

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
    """Every file matching `pattern` under `folder`, following symbolic links,
    which is how Kaggle mounts attached datasets."""
    import fnmatch
    import os

    found = sorted(Path(root) / name for root, _, files in os.walk(folder, followlinks=True)
                   for name in files if fnmatch.fnmatch(name, pattern))
    if not found:
        listing = [str(Path(root).relative_to(folder)) for root, _, _ in os.walk(folder, followlinks=True)][:40]
        raise FileNotFoundError(f"no {pattern} under {folder}; folders: {listing}")
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


# NSL-KDD (Tavallaee et al., 2009): 41 connection features, the label and a difficulty score, no header.
NSLKDD_COLUMNS = (
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
    "hot", "num_failed_logins", "logged_in", "num_compromised", "root_shell", "su_attempted", "num_root",
    "num_file_creations", "num_shells", "num_access_files", "num_outbound_cmds", "is_host_login", "is_guest_login",
    "count", "srv_count", "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate", "same_srv_rate",
    "diff_srv_rate", "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate", "dst_host_srv_rerror_rate", "attack", "difficulty",
)
NSLKDD_CATEGORICAL = ("protocol_type", "service", "flag")


def nslkdd(folder: Path) -> dict:
    """NSL-KDD's official split: KDDTrain+ to train, KDDTest+ to test. Its test set holds 17 attack
    types that never appear in training, by design, so it measures new attacks the way CIC-IDS2017's
    later days do. `family` is the attack name ("normal" for benign), `label` 0/1."""
    def read(pattern: str) -> pd.DataFrame:
        path = _find(folder, pattern)[0]
        frame = pd.read_csv(path, header=None, names=list(NSLKDD_COLUMNS))
        frame["family"] = frame["attack"].astype(str).str.strip()
        frame["label"] = (frame["family"] != "normal").astype(int)
        return frame

    return {"train": read("KDDTrain+.txt"), "test": read("KDDTest+.txt"),
            "files": {"train": "KDDTrain+.txt", "test": "KDDTest+.txt"}}


def nslkdd_features(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The 41 features; categorical ones coded from the training set only (unseen values become -1)."""
    columns = [c for c in NSLKDD_COLUMNS if c not in ("attack", "difficulty")]
    a, b = train[columns].copy(), test[columns].copy()
    for col in NSLKDD_CATEGORICAL:
        codes = {v: i for i, v in enumerate(sorted(a[col].astype(str).unique()))}
        a[col] = a[col].astype(str).map(codes).astype(float)
        b[col] = b[col].astype(str).map(codes).fillna(-1).astype(float)
    return a.astype(float), b.astype(float)


GARBLED_DASH = ("ï¿½", "�", "\x96", "–")
"""CIC's web-attack labels carry an en dash that arrives garbled, depending on
how the CSV was decoded: as U+FFFD, as its UTF-8 bytes read as Latin-1, or as
the Windows-1252 byte."""


def clean_family(label: str) -> str:
    for broken in GARBLED_DASH:
        label = label.replace(broken, "-")
    return " ".join(label.split())


def _day(path: Path) -> str:
    return next((d for d in DAYS if path.name.lower().startswith(d.lower())), "")


def cic(folder: Path) -> pd.DataFrame:
    """Every flow with its `day`, `family` ("BENIGN" for benign) and `label`.
    Column names are stripped of the source's stray spaces. Infinite values,
    which the CSVs contain, become missing."""
    parts = []
    unique = {p.name: p for p in reversed(_find(folder, "*.pcap_ISCX.csv"))}  # a mirror's duplicate copies count once
    paths = sorted(unique.values(), key=lambda p: (DAYS.index(_day(p)) if _day(p) else 9, p.name))
    for path in paths:
        frame = pd.read_csv(path, encoding="latin-1", low_memory=False)
        frame.columns = [c.strip() for c in frame.columns]
        frame["day"] = _day(path)
        parts.append(frame)
    data = pd.concat(parts, ignore_index=True)
    data["family"] = data.pop("Label").astype(str).map(clean_family)
    data["label"] = (data["family"] != "BENIGN").astype(int)
    features = [c for c in data.columns if c not in ("day", "family", "label")]
    data[features] = data[features].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    return data


def cic_features(data: pd.DataFrame) -> list[str]:
    return [c for c in data.columns if c not in ("day", "family", "label")]
