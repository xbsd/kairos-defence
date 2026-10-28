"""Resampling to 1 Hz and kinematic derivatives (SPEC §9.1).

A track's radar points are put on whole UTC seconds from its first to its last point. Seconds inside
a gap longer than ``max_interp_gap_s`` are not interpolated: they are marked ``in_gap`` and every
value there is NaN. Positions are smoothed (centered 3 s median, then centered 3 s mean) inside
gap-free runs only, and derivatives are central differences inside runs (one-sided at run edges).

Units: meters, seconds, degrees. Headings are true bearings clockwise from north in [0, 360); turn
rate is the heading's rate of change in deg/s, wrapped to [-180, 180) then clipped to ±60, so a
counter-clockwise turn (seen from above) is negative.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from kairos_defense import geo

TURN_RATE_CLIP_DPS = 60.0

FEATURE_COLUMNS = [
    "t_s", "ts", "x_m", "y_m", "alt_m", "speed_ms", "vspeed_ms", "heading_deg",
    "turn_rate_dps", "in_gap",
]  # fmt: skip


def epoch_seconds(ts: pd.Series | pd.DatetimeIndex | np.ndarray) -> np.ndarray:
    """Naive-UTC timestamps -> float64 seconds since the Unix epoch."""
    arr = np.asarray(ts, dtype="datetime64[us]")
    return arr.astype(np.int64) / 1e6


def epoch_ms(ts: object) -> int:
    """One naive-UTC timestamp -> int epoch milliseconds (LanceDB ``*_ts_ms`` columns, §7.5)."""
    return int(pd.Timestamp(ts).value // 1_000_000)  # .value is always nanoseconds


def _neighbors(v: np.ndarray, run: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(prev, next)`` of each element of ``v`` (n,), NaN where the neighbor is in another run."""
    prev = np.full_like(v, np.nan)
    nxt = np.full_like(v, np.nan)
    if len(v) > 1:
        same = run[1:] == run[:-1]
        prev[1:] = np.where(same, v[:-1], np.nan)
        nxt[:-1] = np.where(same, v[1:], np.nan)
    return prev, nxt


def _stack3(v: np.ndarray, run: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per element of ``v``: sum, count, max and min of the finite values among (prev, self, next)
    inside its run, as ``(sum, count, max + min)``."""
    prev, nxt = _neighbors(v, run)
    x = np.stack([prev, v, nxt], axis=1)
    ok = np.isfinite(x)
    total = np.where(ok, x, 0.0).sum(axis=1)
    count = ok.sum(axis=1)
    hi = np.where(ok, x, -np.inf).max(axis=1)
    lo = np.where(ok, x, np.inf).min(axis=1)
    return total, count, hi + lo


def _smooth(v: np.ndarray, run: np.ndarray) -> np.ndarray:
    """Centered 3 s rolling median then 3 s rolling mean inside runs (fewer values at run edges,
    as pandas ``rolling(3, center=True, min_periods=1)`` would give)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        total, count, hilo = _stack3(v, run)
        # median of three = sum - max - min; of two (run edge) = their mean; of one = itself
        med = np.where(count == 3, total - hilo, total / count)
        total, count, _ = _stack3(med, run)
        out = total / count
    out[np.isnan(v)] = np.nan
    return out


def _diff(v: np.ndarray, run: np.ndarray, wrap: bool = False) -> np.ndarray:
    """Per-second derivative inside runs: central difference, one-sided at run edges, NaN for a
    run of one second. ``wrap`` treats ``v`` as an angle in degrees."""
    prev, nxt = _neighbors(v, run)

    def d(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return geo.wrap180(b - a) if wrap else b - a

    with np.errstate(invalid="ignore"):
        central = d(prev, nxt) / 2.0
        fwd = d(v, nxt)
        bwd = d(prev, v)
    out = np.where(np.isfinite(central), central, np.where(np.isfinite(fwd), fwd, bwd))
    out[np.isnan(v)] = np.nan
    return out


def resample(points: pd.DataFrame, max_interp_gap_s: float = 10.0) -> pd.DataFrame:
    """Resample one track's points to 1 Hz with derived kinematics.

    ``points`` has columns ``ts`` (naive UTC), ``x_m``, ``y_m``, ``alt_m`` and ``quality``, in any
    order. Returns one row per whole second with ``FEATURE_COLUMNS``: ``t_s`` int seconds since the
    first row, ``ts``, smoothed ``x_m``, ``y_m``, ``alt_m``, ``speed_ms``, ``vspeed_ms``,
    ``heading_deg``, ``turn_rate_dps`` and ``in_gap`` (True where nothing was interpolated).
    """
    empty = pd.DataFrame({c: pd.Series(dtype=float) for c in FEATURE_COLUMNS})
    if len(points) == 0:
        return empty
    s = epoch_seconds(points["ts"])
    p = points
    if not (np.diff(s) > 0).all():  # unsorted or duplicate times: sort, keep the best duplicate
        p = (
            points.sort_values(["ts", "quality"], ascending=[True, False], kind="stable")
            .drop_duplicates("ts", keep="first")
            .reset_index(drop=True)
        )
        s = epoch_seconds(p["ts"])
    grid = np.arange(np.ceil(s[0]), np.floor(s[-1]) + 1.0)
    if len(grid) == 0:
        return empty
    j = np.clip(np.searchsorted(s, grid, side="right") - 1, 0, len(s) - 1)
    j1 = np.minimum(j + 1, len(s) - 1)
    span = s[j1] - s[j]
    in_gap = (span > max_interp_gap_s) & (grid > s[j]) & (grid < s[j1])
    run = np.cumsum(np.r_[True, in_gap[1:] != in_gap[:-1]])

    cols = {}
    for c in ("x_m", "y_m", "alt_m"):
        v = np.interp(grid, s, p[c].to_numpy(dtype=np.float64))
        v[in_gap] = np.nan
        cols[c] = _smooth(v, run)
    dx, dy = _diff(cols["x_m"], run), _diff(cols["y_m"], run)
    with np.errstate(invalid="ignore"):
        heading = geo.wrap360(np.degrees(np.arctan2(dx, dy)))
    heading[np.isnan(dx) | np.isnan(dy)] = np.nan
    turn = np.clip(_diff(heading, run, wrap=True), -TURN_RATE_CLIP_DPS, TURN_RATE_CLIP_DPS)

    t0 = int(grid[0])
    return pd.DataFrame(
        {
            "t_s": (grid - t0).astype(np.int32),
            "ts": pd.to_datetime((grid * 1e6).astype(np.int64), unit="us"),
            "x_m": cols["x_m"],
            "y_m": cols["y_m"],
            "alt_m": cols["alt_m"],
            "speed_ms": np.hypot(dx, dy),
            "vspeed_ms": _diff(cols["alt_m"], run),
            "heading_deg": heading,
            "turn_rate_dps": turn,
            "in_gap": in_gap,
        }
    )
