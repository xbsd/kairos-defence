"""Time-warp lens data (SPEC §16.3 ``dtw`` message, §17.7, D-117): one channel of tonight's window
against a matched flight's anchored segment, with the DTW cost matrix and best path.

Pure numpy over raw channel values (meters, m/s, °/s). Series longer than ``MAX_LEN`` are averaged
down (piecewise aggregate approximation) so the matrix stays ≤ 128 × 128. The band is
``max(|n − m| + 1, ceil(band_fraction × max(n, m)))`` so the corner cell is reachable. The matrix
is ``dtw.warping_paths`` (accumulated cost, ``paths[n, m]`` is the DTW distance) without its padding
row and column, float32 little-endian, row-major, base64. dtaidistance's Python implementation is
used here (a 128 × 128 matrix takes about 5 ms): the C one is avoided for banded matrices
(``dtw_rerank`` docstring).
"""

from __future__ import annotations

import base64
import itertools
import math

import numpy as np
from dtaidistance import dtw

from kairos_defense.features.windows import fill_nan
from kairos_defense.match.dtw_rerank import warp_text

MAX_LEN = 128
CHANNELS = ("speed_ms", "alt_m", "turn_rate_dps", "dist_target_m", "vspeed_ms")


def paa(x: np.ndarray, n: int = MAX_LEN) -> np.ndarray:
    """Average ``x`` down to ``n`` points (equal-width segments); unchanged if not longer."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) <= n:
        return x
    edges = np.linspace(0, len(x), n + 1)
    return np.array([x[int(np.floor(a)) : max(int(np.floor(a)) + 1, int(np.floor(b)))].mean()
                     for a, b in itertools.pairwise(edges)])  # fmt: skip


def band(n: int, m: int, band_fraction: float) -> int:
    return max(abs(n - m) + 1, math.ceil(band_fraction * max(n, m)))


def encode_f32(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype="<f4").tobytes()).decode()


def decode_f32(s: str, shape: tuple[int, int]) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype="<f4").reshape(shape)


def _clean(x: np.ndarray) -> np.ndarray:
    return fill_nan(np.asarray(x, dtype=np.float64).reshape(-1, 1))[:, 0]


def lens_payload(query: np.ndarray, candidate: np.ndarray, *, channel: str, band_fraction: float,
                 warp_ratio: float | None, match_track_id: str) -> dict:  # fmt: skip
    """The ``dtw`` message body for one channel: ``query`` (tonight, ``(n,)``) and ``candidate``
    (the matched segment, ``(m,)``), raw units. NaN gaps are interpolated first."""
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}: one of {', '.join(CHANNELS)}")
    a, b = paa(_clean(query)), paa(_clean(candidate))
    n, m = len(a), len(b)
    if n < 2 or m < 2:
        raise ValueError("the lens needs at least 2 samples on each side")
    w = band(n, m, band_fraction)
    d, paths = dtw.warping_paths(a, b, window=w, use_c=False)
    path = [[int(i), int(j)] for i, j in dtw.best_path(paths)]
    cost = np.where(np.isfinite(paths[1:, 1:]), paths[1:, 1:], np.nan)
    k = min(n, m)
    euclid = float(np.sqrt(np.sum((a[:k] - b[:k]) ** 2)))
    wr = None if warp_ratio is None or not np.isfinite(warp_ratio) else float(warp_ratio)
    return {"match_track_id": match_track_id, "channel": channel,
            "query": [round(float(v), 3) for v in a], "candidate": [round(float(v), 3) for v in b],
            "path": path, "cost": encode_f32(cost), "shape": [n, m], "band": int(w),
            "dtw_distance": float(d), "euclid_distance": euclid, "overlap": k,
            "warp_ratio": wr, "warp_text": warp_text(wr) if wr is not None else None}  # fmt: skip
