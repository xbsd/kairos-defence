"""D-117: the time-warp lens payload (SPEC §16.3 ``dtw``, §17.7)."""

from __future__ import annotations

import numpy as np
import pytest
from dtaidistance import dtw

from kairos_defense.match.lens import MAX_LEN, band, decode_f32, lens_payload, paa


def _lens(a, b, bf=0.1, wr=None):
    return lens_payload(np.asarray(a, float), np.asarray(b, float), channel="dist_target_m",
                        band_fraction=bf, warp_ratio=wr, match_track_id="T-1")  # fmt: skip


def test_path_equals_dtaidistance_best_path() -> None:
    a, b = [0, 1, 2, 3, 2, 1, 0], [0, 0, 1, 2, 3, 3, 2, 1, 0]
    p = _lens(a, b, bf=1.0)
    _, paths = dtw.warping_paths(np.asarray(a, float), np.asarray(b, float), window=p["band"],
                                 use_c=False)  # fmt: skip
    assert p["path"] == [list(x) for x in dtw.best_path(paths)]
    assert p["path"][0] == [0, 0] and p["path"][-1] == [6, 8]
    assert p["dtw_distance"] == pytest.approx(0.0)


def test_cost_is_base64_float32_with_shape() -> None:
    p = _lens(np.arange(10.0), np.arange(12.0) * 0.9)
    cost = decode_f32(p["cost"], tuple(p["shape"]))
    assert cost.dtype == np.float32 and cost.shape == (10, 12)
    assert cost[-1, -1] == pytest.approx(p["dtw_distance"], rel=1e-5)
    assert cost[0, 0] == pytest.approx(0.0)


def test_long_series_averaged_to_128() -> None:
    p = _lens(np.arange(300.0), np.arange(200.0))
    assert p["shape"] == [MAX_LEN, MAX_LEN] and len(p["query"]) == MAX_LEN
    assert paa(np.arange(256.0), 128)[0] == pytest.approx(0.5)
    assert len(paa(np.arange(50.0), 128)) == 50


def test_band_reaches_corner_for_unequal_lengths() -> None:
    assert band(20, 60, 0.1) == 41
    p = _lens(np.zeros(20), np.zeros(60))
    assert p["path"][-1] == [19, 59] and np.isfinite(p["dtw_distance"])


def test_dtw_not_above_euclid_for_equal_lengths() -> None:
    rng = np.random.default_rng(3)
    a, b = np.cumsum(rng.normal(size=40)), np.cumsum(rng.normal(size=40))
    p = _lens(a, b)
    assert p["dtw_distance"] <= p["euclid_distance"] + 1e-9 and p["overlap"] == 40


def test_nan_gaps_are_filled_and_warp_text() -> None:
    a = np.array([1.0, np.nan, 3.0, 4.0])
    p = _lens(a, [1.0, 2.0, 3.0, 4.0], bf=1.0, wr=1.22)
    assert p["query"] == [1.0, 2.0, 3.0, 4.0] and p["warp_text"] == "flown 18% slower"
    assert _lens(a, a, wr=float("nan"))["warp_ratio"] is None


def test_unknown_channel_raises() -> None:
    with pytest.raises(ValueError, match="unknown channel"):
        lens_payload(np.zeros(5), np.zeros(5), channel="color", band_fraction=0.1,
                     warp_ratio=None, match_track_id="T")  # fmt: skip
    with pytest.raises(ValueError, match="2 samples"):
        _lens([1.0], [1.0, 2.0])
