"""Per-service features for one incident, each traceable to the series behind it.

The question a root-cause ranker answers is *which service changed first and
most, relative to its own normal* — so every feature compares a service's
metrics after the fault against the same metrics before it, on that series' own
scale. Absolute values are never features: CPU on Train Ticket and CPU on Sock
Shop are not comparable, and a model that learned their levels would have
learned the systems, not diagnosis (adr/RealDataModels, leave-one-system-out).

Three steps:

1. **Robust shift per series.** `(median_after - median_before) / scale_before`,
   where the scale is the MAD, falling back to the standard deviation. Robust
   because a single spike in the baseline should not hide a real shift.
2. **Log-compressed.** `sign · log1p(|z|)`, because a constant series that moves
   at all produces an enormous z, and an unbounded feature lets one series
   dominate every split.
3. **Ranked within the incident.** Each service's strength is also expressed as
   its percentile among the incident's services, which is the form that
   transfers between systems of different sizes.

Each family feature records the column that produced it, so a ranking can cite
the exact series and window it relied on (rule 1 in CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

#: Metric names vary by system; families are what is comparable across them.
FAMILIES = ("cpu", "mem", "latency", "traffic", "error", "other")


def family(metric: str) -> str:
    name = metric.lower()
    if name.startswith("cpu"):
        return "cpu"
    if name.startswith("mem"):
        return "mem"
    if name.startswith(("latency", "duration")):
        return "latency"
    if name in {"load", "workload"} or name.startswith(("request", "throughput")):
        return "traffic"
    if name.startswith(("error", "fail")):
        return "error"
    return "other"


def split_column(column: str) -> tuple[str, str]:
    """`ts-auth-service_latency-90` → (`ts-auth-service`, `latency-90`)."""
    service, _, metric = column.rpartition("_")
    return (service, metric) if service else (column, "")


@dataclass(frozen=True)
class Window:
    """Seconds of baseline before the fault and of evidence after it."""

    before: int = 600
    after: int = 600
    #: |z| above which a series is said to have moved, for the onset feature.
    onset_z: float = 3.0


def _scale(values: np.ndarray) -> float:
    if values.size < 2:
        return float("nan")
    median = np.median(values)
    mad = 1.4826 * np.median(np.abs(values - median))
    if mad > 0:
        return float(mad)
    std = float(np.std(values))
    if std > 0:
        return std
    # A flat baseline: any movement is a large relative change. Scaled by the
    # level so a flat 0.0 and a flat 900.0 are treated alike.
    return max(abs(float(median)) * 1e-3, 1e-6)


def _compress(z: float) -> float:
    if not np.isfinite(z):
        return float("nan")
    return float(np.sign(z) * np.log1p(abs(z)))


DEFAULT_WINDOW = Window()


def incident_features(
    frame: pd.DataFrame, inject_time: int, window: Window = DEFAULT_WINDOW
) -> tuple[pd.DataFrame, dict[tuple[str, str], str]]:
    """One row per service; and, per (service, feature), the column behind it.

    Missing values are filled within each series only (forward, then back),
    never across services. A case with no baseline before the injection gets
    NaN shift features, which the ranker handles — it is not dropped, because
    dropping hard cases is how a benchmark flatters a model.
    """
    times = frame["time"].to_numpy()
    data = frame.drop(columns=["time"]).ffill().bfill()
    before = (times >= inject_time - window.before) & (times < inject_time)
    after = (times >= inject_time) & (times < inject_time + window.after)

    per_service: dict[str, dict[str, float]] = {}
    provenance: dict[tuple[str, str], str] = {}

    for column in data.columns:
        service, metric = split_column(column)
        fam = family(metric)
        series = data[column].to_numpy(dtype=float)
        base, post = series[before], series[after]
        row = per_service.setdefault(service, {"n_series": 0})
        row["n_series"] += 1
        if base.size < 2 or post.size == 0 or not np.isfinite(base).any():
            continue

        centre, scale = float(np.median(base)), _scale(base)
        if not np.isfinite(scale):
            continue
        z_median = (float(np.median(post)) - centre) / scale
        deviations = (post - centre) / scale
        z_peak = float(np.max(np.abs(deviations)))
        crossed = np.flatnonzero(np.abs(deviations) > window.onset_z)
        onset = float(times[after][crossed[0]] - inject_time) if crossed.size else float(window.after)

        for name, value, larger_is_stronger in (
            (f"shift_{fam}", _compress(z_median), None),
            (f"peak_{fam}", _compress(z_peak), True),
            (f"onset_{fam}", onset, False),
        ):
            current = row.get(name)
            better = (
                current is None
                or (larger_is_stronger is None and abs(value) > abs(current))
                or (larger_is_stronger is True and value > current)
                or (larger_is_stronger is False and value < current)
            )
            if better:
                row[name] = value
                provenance[(service, name)] = column

    table = pd.DataFrame.from_dict(per_service, orient="index")
    table.index.name = "service"
    for fam in FAMILIES:
        for prefix in ("shift", "peak", "onset"):
            if f"{prefix}_{fam}" not in table:
                table[f"{prefix}_{fam}"] = np.nan

    peaks = table[[f"peak_{fam}" for fam in FAMILIES]]
    shifts = table[[f"shift_{fam}" for fam in FAMILIES]].abs()
    onsets = table[[f"onset_{fam}" for fam in FAMILIES]]
    table["peak_any"] = peaks.max(axis=1)
    table["shift_any"] = shifts.max(axis=1)
    table["onset_any"] = onsets.min(axis=1)
    table["families_moved"] = (shifts > np.log1p(window.onset_z)).sum(axis=1)

    # The summary features cite the series of the family that produced them.
    for service, row in table.iterrows():
        for summary, frame_, pick in (
            ("peak_any", peaks, "max"),
            ("shift_any", shifts, "max"),
            ("onset_any", onsets, "min"),
        ):
            values = frame_.loc[service]
            if values.notna().any():
                best = values.idxmax() if pick == "max" else values.idxmin()
                source = provenance.get((service, best))
                if source:
                    provenance[(service, summary)] = source

    # Relative to the other services in this incident — the transferable form.
    for name, ascending in (("peak_any", False), ("shift_any", False), ("onset_any", True)):
        table[f"rank_{name}"] = table[name].rank(ascending=ascending, pct=True, na_option="bottom")
    for fam in FAMILIES:
        table[f"rank_shift_{fam}"] = table[f"shift_{fam}"].abs().rank(
            ascending=False, pct=True, na_option="bottom"
        )
    # No incident-level size feature: it is constant within an incident, so it
    # cannot help rank services, and across systems it fingerprints which
    # system an incident came from — exactly what leave-one-system-out tests.
    return table.reset_index(), provenance


def feature_columns(table: pd.DataFrame) -> list[str]:
    """The model's inputs: everything except identifiers and labels."""
    skip = {"service", "case", "label", "system", "dataset", "fault", "repetition", "root"}
    return [c for c in table.columns if c not in skip]
