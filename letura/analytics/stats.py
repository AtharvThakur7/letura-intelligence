"""Pure statistical helpers (no database access).

MySQL 8 has no PERCENTILE_CONT, so robust statistics are computed here with
pandas/NumPy using linear interpolation (identical to numpy's default).
These functions never drop rows: outliers are *flagged*, not removed.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

SMALL_SAMPLE_THRESHOLD = 10   # n < 10 -> "small sample" warning
VERY_SMALL_SAMPLE = 5         # n < 5  -> statistics shown but flagged as unreliable


def _clean(values: Iterable) -> pd.Series:
    s = pd.to_numeric(pd.Series(list(values) if not isinstance(values, pd.Series) else values), errors="coerce")
    return s.dropna().astype(float)


def describe(values: Iterable, prefix: str = "") -> dict:
    """Robust summary used everywhere: n, mean, median, P25/P75/P90/P95, IQR, min, max."""
    s = _clean(values)
    n = int(s.size)
    keys = ["n", "mean", "median", "p25", "p75", "p90", "p95", "iqr", "min", "max", "std"]
    if n == 0:
        out = {k: (0 if k == "n" else None) for k in keys}
    else:
        q = np.percentile(s.to_numpy(), [25, 50, 75, 90, 95])
        out = {
            "n": n,
            "mean": float(s.mean()),
            "median": float(q[1]),
            "p25": float(q[0]),
            "p75": float(q[2]),
            "p90": float(q[3]),
            "p95": float(q[4]),
            "iqr": float(q[2] - q[0]),
            "min": float(s.min()),
            "max": float(s.max()),
            "std": float(s.std(ddof=1)) if n > 1 else None,
        }
    return {f"{prefix}{k}": v for k, v in out.items()}


def sample_flag(n: int) -> str:
    if n < VERY_SMALL_SAMPLE:
        return "very_small"
    if n < SMALL_SAMPLE_THRESHOLD:
        return "small"
    return "ok"


def iqr_bounds(values: Iterable, k: float = 1.5) -> tuple[float | None, float | None]:
    s = _clean(values)
    if s.empty:
        return None, None
    q1, q3 = np.percentile(s.to_numpy(), [25, 75])
    iqr = q3 - q1
    return float(q1 - k * iqr), float(q3 + k * iqr)


def flag_outliers(values: pd.Series, k: float = 1.5) -> pd.Series:
    """Return a Series of 'low' / 'high' / 'normal' / None (missing). Never drops rows."""
    lo, hi = iqr_bounds(values, k)
    v = pd.to_numeric(values, errors="coerce")
    out = pd.Series("normal", index=values.index, dtype="object")
    out[v.isna()] = None
    if lo is not None:
        out[v < lo] = "low"
        out[v > hi] = "high"
    return out


def safe_round(x, ndigits: int = 2):
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return round(float(x), ndigits)
    except (TypeError, ValueError):
        return None


def grouped_describe(df: pd.DataFrame, by: list[str] | str, value: str = "rent_per_sqm") -> pd.DataFrame:
    """describe() per group, plus sample flag. Keeps empty-safe behaviour."""
    by = [by] if isinstance(by, str) else list(by)
    rows = []
    if df.empty:
        return pd.DataFrame(columns=by + ["n", "mean", "median", "p25", "p75", "p90", "p95", "iqr", "min", "max", "std", "sample_flag"])
    for key, g in df.groupby(by, dropna=False, observed=True, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        d = describe(g[value])
        d.update(dict(zip(by, key)))
        d["sample_flag"] = sample_flag(d["n"])
        rows.append(d)
    out = pd.DataFrame(rows)
    return out[by + [c for c in out.columns if c not in by]]


def pct(part: float, whole: float) -> float | None:
    return None if not whole else round(100.0 * part / whole, 2)


def spearman(x: pd.Series, y: pd.Series) -> float | None:
    """Spearman rank correlation = Pearson on average ranks (no SciPy dependency)."""
    d = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    if len(d) < 3:
        return None
    r = d.iloc[:, 0].rank().corr(d.iloc[:, 1].rank())
    return None if r != r else float(r)
