"""LogHub HDFS_v1 — real Hadoop logs with labelled anomalous blocks.

He et al., *Loghub* (ISSRE 2023), Zenodo record 8196385. 11.2M log lines from
a Hadoop cluster, grouped by HDFS block; each block is labelled normal or
anomalous by the original study (Xu et al., SOSP 2009). The archive ships a
preprocessed form — every block's sequence of log-template ids — which is what
is read here.

**Licence: research or academic use** (datasheets.md). So models trained on it
are evaluated and reported, but their weights are not published until the
owner decides how (adr/RealDataModels).
"""

from __future__ import annotations

import io
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

RECORD = "8196385"
URL = f"https://zenodo.org/records/{RECORD}/files/HDFS_v1.zip?download=1"


def archive(cache: Path) -> Path:
    target = cache / "HDFS_v1.zip"
    if target.exists() and target.stat().st_size > 100_000_000:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    with urllib.request.urlopen(URL, timeout=600) as response, partial.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    partial.replace(target)
    return target


def _read(zf: zipfile.ZipFile, suffix: str) -> pd.DataFrame:
    names = [n for n in zf.namelist() if n.endswith(suffix)]
    if not names:
        raise FileNotFoundError(f"{suffix} not in archive; members: {zf.namelist()[:20]}")
    with zf.open(names[0]) as handle:
        return pd.read_csv(io.BytesIO(handle.read()))


def blocks(cache: Path) -> pd.DataFrame:
    """One row per block, in the order the archive lists them: `block`, `events`
    (list of template ids, in order) and `anomaly` (0/1)."""
    with zipfile.ZipFile(archive(cache)) as zf:
        traces = _read(zf, "Event_traces.csv")
        labels = _read(zf, "anomaly_label.csv")

    block_col = next(c for c in traces.columns if "block" in c.lower())
    seq_col = next(c for c in traces.columns if traces[c].astype(str).str.contains(r"\[?E\d+").any() and c != block_col)
    label_block = next(c for c in labels.columns if "block" in c.lower())
    label_col = next(c for c in labels.columns if c != label_block)

    anomalous = set(labels.loc[labels[label_col].astype(str).str.lower().str.startswith("anom"), label_block])
    pattern = re.compile(r"E\d+")
    out = pd.DataFrame({
        "block": traces[block_col],
        "events": traces[seq_col].astype(str).map(pattern.findall),
    })
    out["anomaly"] = out["block"].isin(anomalous).astype(int)
    return out
