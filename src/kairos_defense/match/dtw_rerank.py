"""DTW re-rank (SPEC §10.4): the only module that imports dtaidistance.

Pure functions over numpy arrays. ``live`` is the query's last W seconds and ``seg`` a candidate's
anchored segment ``[o - 0.5W, o + 1.5W]`` (clipped to the track), both raw ``(n, 5)`` channels in
``scoring.features.channels`` order.

- Shape distance (§10.4 steps 2-4): each series z-normalized over itself and weighted (§9.3), NaN
  filled (0 for a missing channel), banded multichannel DTW with the C library, ``d / sqrt(n)``.
  The segment's two ends may be skipped (psi relaxation, ``m − n`` rows each) when it is longer
  than the live window: the anchor gives room for a warp, and an end-to-end alignment would force
  tonight's W seconds onto all 2W rows, ranking an exact time-warped copy below unrelated flights
  at W = 120 (D-069).
- Warp ratio (step 5, D-069): the same alignment (§9.3 normalization, relaxed ends) gives the
  segment rows that match tonight's window; the pace is tonight's mean speed over the past flight's
  mean speed on those rows. A time warp w multiplies phase durations and divides speeds by w with
  geometry unchanged (§8.5), so this equals w. §10.4's regression of segment index on live index
  was tried first: on real same-actor pairs of the training split it was off by 0.49 (median), the
  speed ratio by 0.09, because orbits carry no timing and the best window often sits at another
  phase. Estimates outside ``WARP_RANGE`` are not credible and become NaN.
  dtaidistance 2.5.1's C ``warping_paths`` returns a wrong matrix near the band edge when given a
  ``window`` (the distance itself is right), so this alignment uses the full matrix.
- The C extension is mandatory (D-013, D-064): ``require_c`` raises ``DtwUnavailable`` and every
  call passes ``use_c=True``.
"""

from __future__ import annotations

import warnings

import numpy as np
from dtaidistance import dtw, dtw_ndim
from dtaidistance.subsequence.dtw import subsequence_alignment

from kairos_defense.features.channels import normalize
from kairos_defense.features.windows import fill_nan

WARP_SLOWER, WARP_FASTER = 1.1, 0.9  # §10.4 step 5: report a pace outside 0.9-1.1
WARP_RANGE = (0.5, 2.0)  # credible relative pace: §8.5 draws w in [0.7, 1.4] (1.4/0.7 = 2)


class DtwUnavailable(RuntimeError):
    """dtaidistance's C extension did not load; pure Python is ~500x slower (D-013)."""


def require_c() -> None:
    """Raise ``DtwUnavailable`` unless dtaidistance's C extension is importable."""
    if not dtw.try_import_c(verbose=False):
        raise DtwUnavailable(
            "dtaidistance's C extension is not available: rebuild it from source "
            "(`uv sync`, with libomp on macOS; D-064)"
        )


def band_window(n: int, m: int, band_fraction: float) -> int:
    """Sakoe-Chiba window: ``int(band_fraction × max(n, m))`` (§10.4 step 3)."""
    return int(band_fraction * max(n, m))


def anchor_bounds(
    offset_s: float, window_s: int, n_rows: int, before: float, after: float
) -> tuple[int, int]:
    """Row slice ``[lo, hi)`` of the anchored segment ``[o − before·W, o + after·W]``, clipped to
    ``[0, n_rows)``. ``offset_s`` is the best window's first row (1 Hz rows from t_s = 0)."""
    lo = int(np.floor(offset_s - before * window_s))
    hi = int(np.ceil(offset_s + after * window_s))
    return max(0, lo), min(n_rows, max(hi, 0))


def prepare(
    raw: np.ndarray,
    weights: np.ndarray | list[float],
    mode: str = "series",
    scales: np.ndarray | list[float] | None = None,
) -> np.ndarray:
    """Scale each channel, weight it, fill NaN (a channel with no value becomes 0); ``(n, c)``
    C-contiguous float64. ``mode`` (D-079): ``series`` z-normalizes over the series (§9.3);
    ``floored`` centers on the series mean but divides by ``max(σ, scale)``, so a near-constant
    channel stays near zero instead of becoming amplified noise; ``fixed`` divides by ``scales``
    without centering. ``floored`` and ``fixed`` need ``scales`` (c,)."""
    x = np.asarray(raw, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    if mode == "series":
        z = normalize(x, w)
    elif mode in ("floored", "fixed"):
        if scales is None:
            raise ValueError(f"DTW normalize={mode!r} needs channel scales")
        sc = np.asarray(scales, dtype=np.float64)
        if mode == "fixed":
            z = x / sc * w
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN channels: filled below
                mu = np.nanmean(x, axis=0)
                sd = np.nanstd(x, axis=0)
            sd = np.where(np.isfinite(sd), np.maximum(sd, sc), sc)
            z = (x - mu) / sd * w
    else:
        raise ValueError(f"unknown DTW normalize mode {mode!r}")
    return np.ascontiguousarray(fill_nan(z), dtype=np.float64)


def relaxation(n: int, m: int) -> tuple[int, int, int, int] | None:
    """psi for aligning all ``n`` live rows to part of an ``m``-row segment: the segment's start and
    end may each skip ``m − n`` rows; None when the segment is not longer."""
    return (0, 0, m - n, m - n) if m > n else None


def shape_distance(
    live: np.ndarray,
    seg: np.ndarray,
    weights: np.ndarray | list[float],
    band_fraction: float,
    mode: str = "series",
    scales: np.ndarray | list[float] | None = None,
) -> float:
    """``d_norm = DTW(L, S) / sqrt(len(L))`` with §9.3 normalization, the §10.4 band and the
    segment's ends relaxed."""
    a, b = prepare(live, weights, mode, scales), prepare(seg, weights, mode, scales)
    n, m = len(a), len(b)
    d = dtw_ndim.distance(a, b, window=band_window(n, m, band_fraction), psi=relaxation(n, m),
                          use_c=True)  # fmt: skip
    return float(d) / np.sqrt(n)


def shape_sim(d_norm: float | np.ndarray, tau: float) -> float | np.ndarray:
    """``exp(−d_norm / τ)`` in (0, 1]."""
    return np.exp(-np.asarray(d_norm, dtype=np.float64) / tau)


def warp_path(live: np.ndarray, seg: np.ndarray, weights: np.ndarray | list[float]) -> np.ndarray:
    """Best alignment of all of ``live`` to part of ``seg`` with §9.3 normalization: ``(p, 2)`` int
    (live row, segment row). The segment's start and end may be skipped (``relaxation``)."""
    a, b = prepare(live, weights), prepare(seg, weights)
    n, m = len(a), len(b)
    psi = relaxation(n, m)
    _, paths = dtw_ndim.warping_paths(a, b, psi=psi, use_c=True)  # full matrix: module docstring
    col = m
    if psi is not None:
        last = paths[n, 1:].copy()
        last[last < 0] = np.inf  # psi-skipped cells are -1
        col = int(np.argmin(last)) + 1
    return np.asarray(dtw.best_path(paths, row=n, col=col), dtype=np.int64)


def warp_ratio(
    live: np.ndarray, seg: np.ndarray, weights: np.ndarray | list[float], speed_col: int = 0
) -> float:
    """Pace of the past flight relative to tonight (``> 1``: it flew slower and took longer):
    tonight's mean speed over the past flight's mean speed on the segment rows aligned with
    tonight's window. NaN when either series has under 2 rows, a speed is missing, or the estimate
    is outside ``WARP_RANGE``."""
    if len(live) < 2 or len(seg) < 2:
        return float("nan")
    rows = np.unique(warp_path(live, seg, weights)[:, 1])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        v_live = np.nanmean(np.asarray(live, dtype=np.float64)[:, speed_col])
        v_past = np.nanmean(np.asarray(seg, dtype=np.float64)[rows, speed_col])
    if not (np.isfinite(v_live) and np.isfinite(v_past)) or v_live <= 0 or v_past <= 0:
        return float("nan")
    k = float(v_live / v_past)
    return k if WARP_RANGE[0] <= k <= WARP_RANGE[1] else float("nan")


def warp_text(k: float) -> str | None:
    """Pace text: "flown X% slower" (k > 1.1, X = round((1 − 1/k)·100)), "flown X% faster"
    (k < 0.9, X = round((1/k − 1)·100), the mirror of §10.4's formula), else None."""
    if not np.isfinite(k) or k <= 0:
        return None
    if k > WARP_SLOWER:
        return f"flown {round((1 - 1 / k) * 100)}% slower"
    if k < WARP_FASTER:
        return f"flown {round((1 / k - 1) * 100)}% faster"
    return None


def explain_alignment(live_dist: np.ndarray, full_dist: np.ndarray) -> tuple[int, int, float]:
    """Where tonight's ``dist_target_m`` window falls inside a whole past flight (§10.4 step 6, for
    the phase 8 Match Explainer): ``(first row, last row, DTW value)`` of the best subsequence.
    Raw meters on both sides; NaN filled by interpolation."""
    q = fill_nan(np.asarray(live_dist, dtype=np.float64).reshape(-1, 1))[:, 0]
    s = fill_nan(np.asarray(full_dist, dtype=np.float64).reshape(-1, 1))[:, 0]
    sa = subsequence_alignment(np.ascontiguousarray(q), np.ascontiguousarray(s), use_c=True)
    match = sa.best_match()
    start, end = match.segment
    return int(start), int(end), float(match.value)
