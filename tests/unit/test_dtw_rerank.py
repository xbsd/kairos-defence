"""SPEC §10.4 DTW re-rank: C path, band, anchors, normalization, warp ratio (D-069)."""

from __future__ import annotations

import numpy as np
import pytest
from dtaidistance import dtw, dtw_ndim

from kairos_defense.match import dtw_rerank as dr

WEIGHTS = [1.0, 1.0, 1.2, 0.6, 0.4]


def flight(t: np.ndarray) -> np.ndarray:
    """A five-channel synthetic flight: approach for 100 s, then an orbit; ``(n, 5)``."""
    t = np.asarray(t, dtype=np.float64)
    speed = np.where(t < 100, 15 - 0.05 * t, 10 + 1.5 * np.sin(t / 17.0))
    turn = np.where(t < 100, 0.5 * np.sin(t / 9.0), -3.2 + 0.8 * np.sin(t / 11.0))
    dist = np.where(t < 100, 1500 - 13 * t, 200 + 25 * np.sin(t / 23.0))
    alt = 100 + 8 * np.sin(t / 31.0)
    vs = 0.6 * np.cos(t / 13.0)
    return np.c_[speed, turn, dist, alt, vs]


def other_flight(t: np.ndarray) -> np.ndarray:
    """An unrelated pass: straight, fast, steady altitude."""
    t = np.asarray(t, dtype=np.float64)
    return np.c_[20 + np.sin(t / 40), 0.2 * np.cos(t / 6), 2000 - 8 * t, 60 + t / 20,
                 0.1 * np.sin(t / 3)]  # fmt: skip


def warped(f, t: np.ndarray, warp: float) -> np.ndarray:
    """§8.5: a copy flown ``warp`` times as long: same geometry, every rate (speed, turn rate,
    climb rate) divided by ``warp``."""
    x = f(np.asarray(t, dtype=np.float64) / warp)
    x[:, [0, 1, 4]] /= warp
    return x


def live_and_segment(warp: float, w: int, a0: int = 150, f=flight):
    """Tonight's window ``[a0, a0 + W)`` and the anchored segment of a copy flown ``warp`` times
    as long, around the copy's matching offset."""
    live = flight(np.arange(a0, a0 + w))
    o = round(warp * a0)
    lo, hi = dr.anchor_bounds(o, w, 10_000, 0.5, 1.5)
    return live, warped(f, np.arange(lo, hi), warp)


def test_require_c_fails_loudly(monkeypatch) -> None:
    dr.require_c()  # the real library has its C extension (D-064)
    monkeypatch.setattr(dr.dtw, "try_import_c", lambda verbose=False: False)
    with pytest.raises(dr.DtwUnavailable, match="C extension"):
        dr.require_c()


def test_self_distance_is_zero() -> None:
    x = flight(np.arange(150, 270))
    d = dr.shape_distance(x, x, WEIGHTS, 0.25)
    assert d == pytest.approx(0.0, abs=1e-9)
    assert dr.shape_sim(d, 1.0) == pytest.approx(1.0)
    # the C result equals pure Python on a small case
    rng = np.random.default_rng(5)
    a, b = rng.normal(size=(30, 5)), rng.normal(size=(50, 5))
    c = dtw_ndim.distance(a, b, window=12, use_c=True)
    py = dtw_ndim.distance(a, b, window=12, use_c=False)
    assert c == pytest.approx(py, rel=1e-12)


def test_band_window() -> None:
    assert dr.band_window(60, 120, 0.25) == 30
    assert dr.band_window(120, 61, 0.25) == 30
    assert dr.band_window(46, 120, 0.25) == 30
    assert dr.band_window(10, 10, 0.25) == 2


def test_anchor_bounds_clip_to_the_track() -> None:
    assert dr.anchor_bounds(0, 60, 400, 0.5, 1.5) == (0, 90)  # start: clipped at 0
    assert dr.anchor_bounds(200, 60, 400, 0.5, 1.5) == (170, 290)  # middle: 2W rows
    assert dr.anchor_bounds(350, 60, 400, 0.5, 1.5) == (320, 400)  # end: clipped at n
    assert dr.anchor_bounds(100, 120, 1000, 0.5, 1.5) == (40, 280)


def test_nan_and_missing_channel() -> None:
    x = flight(np.arange(150, 270))
    x[10:14, 0] = np.nan  # short hole: interpolated
    x[:, 4] = np.nan  # missing channel: zeros
    p = dr.prepare(x, WEIGHTS)
    assert np.isfinite(p).all() and np.allclose(p[:, 4], 0.0)
    assert p.flags["C_CONTIGUOUS"] and p.dtype == np.float64
    assert np.isfinite(dr.shape_distance(x, flight(np.arange(100, 300)), WEIGHTS, 0.25))
    assert np.isfinite(dr.warp_ratio(x, flight(np.arange(100, 300)), WEIGHTS))


@pytest.mark.parametrize("w", [60, 120])
@pytest.mark.parametrize("warp", [0.8, 0.95, 1.0, 1.22, 1.4])
def test_time_warped_copy_scores_high_and_reports_its_warp(warp: float, w: int) -> None:
    live, seg = live_and_segment(warp, w)
    _, unrelated = live_and_segment(warp, w, f=other_flight)
    tau = 1.0
    sim = dr.shape_sim(dr.shape_distance(live, seg, WEIGHTS, 0.25), tau)
    other = dr.shape_sim(dr.shape_distance(live, unrelated, WEIGHTS, 0.25), tau)
    assert sim > 1.3 * other  # clearly above an unrelated flight at any τ near 1
    # speed ratio over the aligned rows (D-069): within 0.2% at W = 120; at W = 60 the window holds
    # less than one cycle of the orbit's speed wobble and reads up to 4.3% low
    assert dr.warp_ratio(live, seg, WEIGHTS) == pytest.approx(warp, rel=0.05)


def test_warp_text() -> None:
    assert dr.warp_text(1.22) == "flown 18% slower"
    assert dr.warp_text(0.8) == "flown 25% faster"
    assert dr.warp_text(1.05) is None and dr.warp_text(0.95) is None
    assert dr.warp_text(float("nan")) is None


def test_warp_outside_the_credible_range_is_nan() -> None:
    live = flight(np.arange(150, 210))
    seg = flight(np.arange(120, 240))
    assert dr.warp_ratio(live, seg, WEIGHTS) == pytest.approx(1.0, rel=0.05)
    fast = seg.copy()
    fast[:, 0] *= 3.0  # past flight three times as fast: not a credible pace (§8.5)
    assert np.isnan(dr.warp_ratio(live, fast, WEIGHTS))
    stopped = seg.copy()
    stopped[:, 0] = np.nan
    assert np.isnan(dr.warp_ratio(live, stopped, WEIGHTS))


def test_short_segment_has_no_relaxation(monkeypatch) -> None:
    calls = []
    real = dtw_ndim.warping_paths

    def spy(*a, **k):
        calls.append(k.get("psi"))
        return real(*a, **k)

    monkeypatch.setattr(dr.dtw_ndim, "warping_paths", spy)
    live = flight(np.arange(150, 210))
    k = dr.warp_ratio(live, flight(np.arange(160, 200)), WEIGHTS)  # m = 40 <= n = 60
    assert np.isfinite(k) and calls == [None]
    dr.warp_ratio(live, flight(np.arange(120, 240)), WEIGHTS)
    assert calls[-1] == (0, 0, 60, 60)
    assert np.isnan(dr.warp_ratio(live[:1], live, WEIGHTS))


def test_banded_c_distance_with_psi_matches_python() -> None:
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=(60, 5)), rng.normal(size=(120, 5))
    for win in (30, 45):
        c = dtw_ndim.distance(a, b, window=win, psi=(0, 0, 60, 60), use_c=True)
        assert c == pytest.approx(dtw_ndim.distance(a, b, window=win, psi=(0, 0, 60, 60)))


def test_relaxed_ends_rank_the_warped_copy_first() -> None:
    """D-069: without psi, an exact copy flown at tonight's pace scores below an unrelated flight
    at W = 120 (all of its 2W rows are forced onto tonight's W)."""
    live, seg = live_and_segment(1.0, 120)
    _, unrelated = live_and_segment(1.0, 120, f=other_flight)
    a, s, u = (dr.prepare(x, WEIGHTS) for x in (live, seg, unrelated))
    end_to_end = [dtw_ndim.distance(a, x, window=60, use_c=True) for x in (s, u)]
    assert end_to_end[0] > end_to_end[1]  # the spec's literal reading fails here
    assert dr.shape_distance(live, seg, WEIGHTS, 0.25) < dr.shape_distance(
        live, unrelated, WEIGHTS, 0.25
    )


def test_c_paths_match_python_without_band() -> None:
    """D-069: the warp alignment's C paths matrix (full, psi-relaxed) equals pure Python's."""
    rng = np.random.default_rng(3)
    a, b = rng.normal(size=(40, 5)), rng.normal(size=(80, 5))
    psi = (0, 0, 40, 40)
    dc, pc = dtw_ndim.warping_paths(a, b, psi=psi, use_c=True)
    dp, pp = dtw_ndim.warping_paths(a, b, psi=psi, use_c=False)
    assert dc == pytest.approx(dp) and np.allclose(pc, pp, equal_nan=True)
    assert dtw.best_path(pc, row=40, col=60) == dtw.best_path(pp, row=40, col=60)


def test_explain_alignment_finds_the_window() -> None:
    full = flight(np.arange(0, 500))[:, 2]  # end of the approach, start of the orbit: unique
    start, end, value = dr.explain_alignment(full[60:120], full)
    assert abs(start - 60) <= 3 and abs(end - 119) <= 3 and value >= 0
    slow = warped(flight, np.arange(0, 600), 1.2)[:, 2]  # past flight flown 1.2x as long
    start, end, _ = dr.explain_alignment(full[60:120], slow)
    assert abs(start - 72) <= 3 and abs(end - 143) <= 4
