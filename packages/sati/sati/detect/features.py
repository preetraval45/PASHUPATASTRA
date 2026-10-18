"""Causal features for Shailaputri — each point judged only against its past.

A detector is run online in production: when a value arrives, only earlier
values exist. Every feature here is computed from `x[:t]` plus `x[t]` itself —
the rolling statistics are shifted by one so the current point never sits in
its own baseline. That is what lets the features be computed for a whole series
at once (fast) while meaning exactly what they would mean online (honest).

No global normalisation: every scale is the series' own recent past, so a
feature means the same on a CPU percentage and a tweet count, which is what a
model tested on a family of series it never trained on needs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WINDOWS = (12, 72, 288)
"""Short, medium and long baselines. At NAB's typical 5-minute interval these
are an hour, six hours and a day."""
WARMUP = max(WINDOWS) + 1
"""Points with no long baseline yet are not judged — the same rule the
statistical strategies follow, and not credited or penalised by `evaluate`."""


def _scale(series: pd.Series, window: int) -> pd.Series:
    """Robust scale from the inter-quartile range, falling back to the std."""
    past = series.shift(1).rolling(window, min_periods=window)
    iqr = (past.quantile(0.75) - past.quantile(0.25)) / 1.349
    std = past.std()
    scale = iqr.where(iqr > 0, std)
    level = series.shift(1).rolling(window, min_periods=window).median().abs()
    return scale.where(scale > 0, (level * 1e-3).clip(lower=1e-6))


def _compress(z: pd.Series) -> pd.Series:
    return np.sign(z) * np.log1p(z.abs())


def features(values: np.ndarray) -> pd.DataFrame:
    x = pd.Series(np.asarray(values, dtype=float)).ffill().bfill()
    out: dict[str, pd.Series] = {}
    for w in WINDOWS:
        centre = x.shift(1).rolling(w, min_periods=w).median()
        out[f"z_{w}"] = _compress((x - centre) / _scale(x, w))
    d = x.diff()
    centre_d = d.shift(1).rolling(WINDOWS[1], min_periods=WINDOWS[1]).median()
    out["z_diff"] = _compress((d - centre_d) / _scale(d, WINDOWS[1]))
    short = x.shift(1).rolling(WINDOWS[0], min_periods=WINDOWS[0]).std()
    long = x.shift(1).rolling(WINDOWS[2], min_periods=WINDOWS[2]).std()
    out["volatility_ratio"] = np.log1p((short / long.replace(0, np.nan)).fillna(0))
    # Same time one long window ago — "yesterday", for daily-shaped series.
    out["z_season"] = _compress((x - x.shift(WINDOWS[2])) / _scale(x, WINDOWS[2]))
    frame = pd.DataFrame(out)
    frame["abs_max"] = frame[[f"z_{w}" for w in WINDOWS]].abs().max(axis=1)
    return frame.replace([np.inf, -np.inf], np.nan)


def labels(length: int, ranges: list[tuple[int, int]]) -> np.ndarray:
    y = np.zeros(length, dtype=int)
    for start, end in ranges:
        y[start:end] = 1
    return y
