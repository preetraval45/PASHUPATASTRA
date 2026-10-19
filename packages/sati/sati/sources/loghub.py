"""LogHub HDFS_v1 and BGL — real system logs with labelled anomalies.

He et al., *Loghub* (ISSRE 2023), Zenodo record 8196385. 11.2M log lines from
a Hadoop cluster, grouped by HDFS block; each block is labelled normal or
anomalous by the original study (Xu et al., SOSP 2009). The archive ships a
preprocessed form — every block's sequence of log-template ids — which is what
is read here.

BGL is 4.7M lines from the BlueGene/L supercomputer at Lawrence Livermore
(Oliner & Stearley, DSN 2007). Every line carries an alert label, set by the
system's administrators: `-` for none, a category such as `KERNDTLB` for an
alert. It ships raw, so `bgl_windows` parses templates and groups lines itself.

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
BGL_URL = f"https://zenodo.org/records/{RECORD}/files/BGL.zip?download=1"


def archive(cache: Path, url: str = URL, name: str = "HDFS_v1.zip", minimum: int = 100_000_000) -> Path:
    target = cache / name
    if target.exists() and target.stat().st_size > minimum:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=600) as response, partial.open("wb") as out:
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


DIGITS = re.compile(r"\d")


def bgl_line(line: str) -> tuple[int, str] | None:
    """`(anomaly, template)` for one BGL line, or None if it is malformed.

    The fields are: label, epoch, date, node, time, node again, type,
    component, level, then the message. The template is the message with every
    token that contains a digit replaced by `<*>`. Addresses, counts, core
    numbers and timestamps vary while the event stays the same. The level
    (INFO, FATAL…) is not used: the template is what the system said, not how
    loudly.
    """
    parts = line.rstrip("\r\n").split(" ", 9)
    if len(parts) < 10:
        return None
    template = " ".join("<*>" if DIGITS.search(tok) else tok for tok in parts[9].split())
    return int(parts[0] != "-"), template


def bgl_windows(cache: Path, size: int = 100) -> pd.DataFrame:
    """BGL as fixed windows of `size` consecutive lines, in log order.

    Each row has `block` (the window index), `events` (template ids in order)
    and `anomaly`: 1 if any line in the window carries an alert label. The
    columns are the same as `blocks`, so the same model and baselines read
    both datasets.
    """
    ids: dict[str, str] = {}
    rows, events, anomalous = [], [], 0
    with zipfile.ZipFile(archive(cache, BGL_URL, "BGL.zip", 50_000_000)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".log"))
        with zf.open(name) as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8", errors="replace"):
                parsed = bgl_line(line)
                if parsed is None:
                    continue
                label, template = parsed
                events.append(ids.setdefault(template, f"T{len(ids)}"))
                anomalous |= label
                if len(events) == size:
                    rows.append((len(rows), events, anomalous))
                    events, anomalous = [], 0
    return pd.DataFrame(rows, columns=["block", "events", "anomaly"])
