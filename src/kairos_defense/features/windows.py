"""Sliding windows and PAA vectors (SPEC §9.5).

A window is ``W`` consecutive 1 Hz feature rows. Its vector: take the (W, 5) channel matrix,
z-normalize and weight each channel over the window (§9.3), fill NaN by linear interpolation along
time (0 for a channel with no value), average into 16 equal segments (piecewise aggregate
approximation, exact for fractional segment lengths), flatten channel-major (all 16 segments of
channel 0, then channel 1, ...), L2-normalize and store as float32 (D-051).

A live query uses the same function on its most recent W seconds, with W the largest window size
not longer than what has been seen; before the smallest size is reached it uses everything seen so
far against the smallest size (D-050).
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import SIGMA_FLOOR, channel_matrix

MAX_GAP_FRACTION = 0.2  # skip windows with more gap seconds than this


@lru_cache(maxsize=64)
def paa_weights(n: int, segments: int) -> np.ndarray:
    """``(segments, n)`` float64 averaging matrix: row k averages the samples overlapping
    ``[k n/segments, (k+1) n/segments)``, weighting partly covered samples by their overlap."""
    if n <= 0 or segments <= 0:
        raise ValueError("PAA needs n > 0 and segments > 0")
    edges = np.arange(segments + 1) * (n / segments)
    lo, hi = edges[:-1, None], edges[1:, None]
    i = np.arange(n)[None, :]
    overlap = np.clip(np.minimum(hi, i + 1) - np.maximum(lo, i), 0.0, None)
    w = overlap / (n / segments)
    w.setflags(write=False)
    return w


def _fill_nan(z: np.ndarray) -> np.ndarray:
    """Linear interpolation along axis 0 per column (edges take the nearest value); a column with
    no finite value becomes 0 (its mean after normalization)."""
    out = z.copy()
    t = np.arange(len(z))
    for c in range(z.shape[1]):
        col = out[:, c]
        bad = ~np.isfinite(col)
        if not bad.any():
            continue
        if bad.all():
            col[:] = 0.0
        else:
            col[bad] = np.interp(t[bad], t[~bad], col[~bad])
    return out


def window_vectors(
    raw: np.ndarray,
    size: int,
    offsets: np.ndarray | list[int],
    weights: np.ndarray | list[float],
    segments: int,
) -> np.ndarray:
    """Vectors of the windows ``raw[o : o + size]`` for each offset: ``(k, c * segments)`` float32,
    unit length. ``raw`` is ``(n, c)`` raw channels; all windows are processed together."""
    offsets = np.asarray(offsets, dtype=np.int64)
    win = np.moveaxis(sliding_window_view(raw, size, axis=0)[offsets], -1, 1)  # (k, size, c)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN channels: handled below
        mu = np.nanmean(win, axis=1, keepdims=True)
        sd = np.nanstd(win, axis=1, keepdims=True)
    sd = np.where(np.isfinite(sd), np.maximum(sd, SIGMA_FLOOR), SIGMA_FLOOR)
    z = (win - mu) / sd * np.asarray(weights, dtype=np.float64)
    for i in np.flatnonzero(~np.isfinite(z).all(axis=(1, 2))):
        z[i] = _fill_nan(z[i])
    paa = np.einsum("ms,ksc->kcm", paa_weights(size, segments), z)  # (k, c, segments)
    v = paa.reshape(len(offsets), -1)  # channel-major
    norm = np.linalg.norm(v, axis=1, keepdims=True)
    return (v / np.where(norm > 0, norm, 1.0)).astype(np.float32)


def window_vector(raw: np.ndarray, weights: np.ndarray | list[float], segments: int) -> np.ndarray:
    """Raw channels ``(n, c)`` of one window -> ``(c * segments,)`` float32 unit vector."""
    return window_vectors(np.asarray(raw, dtype=np.float64), len(raw), [0], weights, segments)[0]


@dataclass(frozen=True)
class Window:
    window_s: int
    offset_s: int  # first row's t_s
    vector: np.ndarray  # (c * segments,) float32


def iter_windows(features: pd.DataFrame, scoring: ScoringConfig) -> Iterator[Window]:
    """Every §9.5 window of one track: each size in ``sizes_s``, offsets 0, stride, 2 x stride ...
    while the window fits; windows with more than 20% gap seconds are skipped."""
    raw = channel_matrix(features, scoring)
    gap = features["in_gap"].to_numpy(dtype=bool)
    t_s = features["t_s"].to_numpy()
    cum_gap = np.r_[0, np.cumsum(gap)]
    for size in scoring.windows.sizes_s:
        offs = np.arange(0, len(raw) - size + 1, scoring.windows.stride_s)
        offs = offs[(cum_gap[offs + size] - cum_gap[offs]) <= MAX_GAP_FRACTION * size]
        if len(offs) == 0:
            continue
        vecs = window_vectors(raw, size, offs, scoring.features.channel_weights,
                              scoring.windows.paa_segments)  # fmt: skip
        for o, v in zip(offs, vecs, strict=True):
            yield Window(size, int(t_s[o]), v)


def query_window_size(n_seconds: int, scoring: ScoringConfig) -> int:
    """W for a live query that has ``n_seconds`` rows: the largest size not above it, else the
    smallest size (the query then uses all its rows, D-050)."""
    sizes = sorted(scoring.windows.sizes_s)
    fitting = [s for s in sizes if s <= n_seconds]
    return fitting[-1] if fitting else sizes[0]


def query_vector(features: pd.DataFrame, scoring: ScoringConfig) -> tuple[np.ndarray, int, int]:
    """Vector of a (partial) track's most recent W seconds: ``(vector, W, rows used)``."""
    if len(features) == 0:
        raise ValueError("no features to build a query from")
    size = query_window_size(len(features), scoring)
    tail = features.iloc[-size:]
    raw = channel_matrix(tail, scoring)
    vec = window_vector(raw, scoring.features.channel_weights, scoring.windows.paa_segments)
    return vec, size, len(tail)
