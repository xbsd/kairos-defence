"""SPEC §9.5 windows and PAA vectors (D-050, D-051)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.windows import (
    iter_windows,
    paa_weights,
    query_vector,
    query_window_size,
    window_vector,
)


def test_paa_weights_known_answers() -> None:
    w = paa_weights(64, 16)
    assert w.shape == (16, 64) and np.allclose(w.sum(axis=1), 1.0)
    assert np.allclose(w[0, :4], 0.25) and np.allclose(w[0, 4:], 0.0)
    w = paa_weights(60, 16)  # 3.75 s per segment
    assert np.allclose(w.sum(axis=1), 1.0)
    ramp = np.arange(60.0)
    assert np.isclose((w @ ramp)[0], (0 + 1 + 2 + 0.75 * 3) / 3.75)  # 3 whole samples + 3/4 of one
    assert np.allclose(w @ ramp, (np.arange(16) + 0.5) * 3.75 - 0.5, atol=0.05)
    assert np.allclose(paa_weights(45, 16).sum(axis=1), 1.0)  # shorter than 60: still exact


def test_window_vector_shape_norm_and_channel_order() -> None:
    raw = np.zeros((60, 5))
    raw[:, 0] = np.arange(60.0)  # only channel 0 varies; the rest normalize to 0
    v = window_vector(raw, [1.0, 1.0, 1.2, 0.6, 0.4], 16)
    assert v.dtype == np.float32 and v.shape == (80,)
    assert np.isclose(np.linalg.norm(v), 1.0, atol=1e-6)
    assert np.all(np.diff(v[:16]) > 0) and np.allclose(v[16:], 0.0)  # channel-major


def test_weights_scale_channels() -> None:
    rng = np.random.default_rng(1)
    raw = rng.normal(size=(120, 2))
    a = window_vector(raw, [1.0, 1.0], 16)
    b = window_vector(raw, [1.0, 2.0], 16)
    ratio = np.linalg.norm(b[16:]) / np.linalg.norm(b[:16])
    assert np.isclose(ratio, 2.0 * np.linalg.norm(a[16:]) / np.linalg.norm(a[:16]))


def test_nan_handling() -> None:
    rng = np.random.default_rng(2)
    raw = rng.normal(size=(60, 3))
    raw[10:14, 0] = np.nan  # short hole: interpolated
    raw[:, 2] = np.nan  # missing channel: zeros
    v = window_vector(raw, [1.0, 1.0, 1.0], 16)
    assert np.isfinite(v).all() and np.allclose(v[32:], 0.0)


CHANNELS = ["speed_ms", "turn_rate_dps", "dist_target_m", "alt_m", "vspeed_ms"]


def _features(n: int, gap: slice | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    f = pd.DataFrame(rng.normal(size=(n, 5)), columns=CHANNELS)
    f["t_s"] = np.arange(n)
    f["in_gap"] = False
    if gap is not None:
        f.loc[f.index[gap], "in_gap"] = True
        f.loc[
            f.index[gap], ["speed_ms", "turn_rate_dps", "dist_target_m", "alt_m", "vspeed_ms"]
        ] = np.nan
    return f


def test_window_offsets_and_sizes(cfg) -> None:
    ws = list(iter_windows(_features(400), cfg.scoring))
    by = {s: [w.offset_s for w in ws if w.window_s == s] for s in (60, 120, 300)}
    assert by[60] == list(range(0, 341, 10))
    assert by[120] == list(range(0, 281, 10))
    assert by[300] == list(range(0, 101, 10))


def test_gappy_windows_are_skipped(cfg) -> None:
    ws = list(iter_windows(_features(200, gap=slice(100, 125)), cfg.scoring))  # 25 gap seconds
    w60 = {w.offset_s for w in ws if w.window_s == 60}
    assert 80 not in w60 and 90 not in w60  # > 20% of 60 s in the gap
    assert 0 in w60 and 130 in w60
    assert all(np.isfinite(w.vector).all() for w in ws)


@pytest.mark.parametrize(
    ("n", "size"),
    [(30, 60), (46, 60), (60, 60), (61, 60), (119, 60), (121, 120), (299, 120), (300, 300),
     (900, 300)],
)  # fmt: skip
def test_query_window_size(cfg, n: int, size: int) -> None:
    assert query_window_size(n, cfg.scoring) == size


def test_query_vector_equals_indexed_window(cfg) -> None:
    f = _features(400)
    indexed = {(w.window_s, w.offset_s): w.vector for w in iter_windows(f, cfg.scoring)}
    vec, size, used = query_vector(f.iloc[: 150 + 120], cfg.scoring)  # 270 rows -> W = 120
    assert (size, used) == (120, 120)
    assert np.array_equal(vec, indexed[(120, 150)])
    vec, size, used = query_vector(f.iloc[:46], cfg.scoring)  # T = 45: all rows vs W = 60
    assert (size, used) == (60, 46) and vec.shape == (80,)


def _with_normalize(cfg, mode: str):
    win = cfg.scoring.windows.model_copy(update={"normalize": mode})
    return cfg.scoring.model_copy(update={"windows": win})


def test_fixed_scaling_keeps_levels(cfg) -> None:
    """Same shape at 180 m and 1,800 m: identical under per-window z, different under fixed units
    (D-068: the orbit radius must survive into the prefilter vector)."""
    t = np.arange(60.0)
    near = np.c_[10 + np.sin(t / 7), -3 + np.cos(t / 5), 180 + 20 * np.sin(t / 9),
                 100 + t / 10, np.cos(t / 4)]  # fmt: skip
    far = near.copy()
    far[:, 2] *= 10.0
    w, scales = cfg.scoring.features.channel_weights, cfg.scoring.features.channel_scales
    assert np.allclose(window_vector(near, w, 16), window_vector(far, w, 16), atol=1e-6)
    a, b = window_vector(near, w, 16, scales), window_vector(far, w, 16, scales)
    assert np.isclose(np.linalg.norm(a), 1.0, atol=1e-6) and np.linalg.norm(a - b) > 0.5
    # fixed units: proportional to raw / scale x weight (before the final L2 normalization)
    expect = near / np.asarray(scales) * np.asarray(w)
    paa = paa_weights(60, 16) @ expect
    v = paa.T.reshape(-1)
    assert np.allclose(a, v / np.linalg.norm(v), atol=1e-6)


@pytest.mark.parametrize("mode", ["window", "fixed"])
def test_query_vector_equals_indexed_window_both_modes(cfg, mode: str) -> None:
    sc = _with_normalize(cfg, mode)
    f = _features(400)
    indexed = {(w.window_s, w.offset_s): w.vector for w in iter_windows(f, sc)}
    vec, size, used = query_vector(f.iloc[: 150 + 120], sc)
    assert (size, used) == (120, 120) and np.array_equal(vec, indexed[(120, 150)])
    vec45, size, used = query_vector(f.iloc[:46], sc)  # T = 45: all rows vs W = 60
    assert (size, used) == (60, 46) and vec45.shape == (80,)
    other = _with_normalize(cfg, "fixed" if mode == "window" else "window")
    assert not np.allclose(vec, query_vector(f.iloc[:270], other)[0])  # the modes really differ


def test_fixed_mode_nan_handling(cfg) -> None:
    rng = np.random.default_rng(4)
    raw = rng.normal(size=(60, 5)) + 5
    raw[10:14, 0] = np.nan
    raw[:, 4] = np.nan
    v = window_vector(raw, [1.0] * 5, 16, [1.0] * 5)
    assert np.isfinite(v).all() and np.allclose(v[64:], 0.0)
