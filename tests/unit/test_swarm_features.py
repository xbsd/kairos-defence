"""Swarm descriptors (SPEC §14): known answers on hand-made formations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.swarm_features import (
    DESCRIPTOR_COLUMNS,
    SERIES_COLUMNS,
    detect_swarm,
    drone_grid,
    longest_run,
    principal_axis_deg,
    swarm_descriptors,
    swarm_series,
    swarm_vector,
    unwrap_axis,
)


def formation_track(offsets: np.ndarray, n: int, velocity=(0.0, 0.0), turn_dps: float = 0.0,
                    origin=(1000.0, 2000.0)) -> np.ndarray:  # fmt: skip
    """``(d, n, 3)`` positions: ``offsets`` (d, 2) turned clockwise by ``turn_dps`` per second
    about a centroid moving at ``velocity`` (m/s) from ``origin``; altitude 90 m."""
    t = np.arange(n, dtype=np.float64)
    ang = np.radians(turn_dps * t)  # clockwise
    c, s = np.cos(ang), np.sin(ang)
    x = offsets[:, 0, None] * c[None] + offsets[:, 1, None] * s[None]
    y = -offsets[:, 0, None] * s[None] + offsets[:, 1, None] * c[None]
    cx = origin[0] + velocity[0] * t
    cy = origin[1] + velocity[1] * t
    return np.stack([x + cx[None], y + cy[None], np.full_like(x, 90.0)], axis=2)


SQUARE = np.array([[-20.0, -20.0], [20.0, -20.0], [20.0, 20.0], [-20.0, 20.0]])


def test_descriptors_of_a_square_formation() -> None:
    pos = formation_track(SQUARE, 30, velocity=(3.0, 4.0))
    d = swarm_descriptors(np.arange(30), pos, np.array([1000.0, 2000.0]), min_drones=3)
    assert list(d.columns) == DESCRIPTOR_COLUMNS and len(d) == 30
    assert np.allclose(d.spread_m, 40.0 / np.sqrt(2))  # each corner is 20√2 m from the center
    # six pairs: four 40 m sides and two 40√2 m diagonals -> linear quartiles
    pairs = np.sort([40.0] * 4 + [40.0 * np.sqrt(2)] * 2)
    q = np.quantile(pairs, [0.25, 0.5, 0.75])
    assert np.allclose(d.pd_q25_m, q[0]) and np.allclose(d.pd_q50_m, q[1])
    assert np.allclose(d.pd_q75_m, q[2])
    assert np.allclose(d.centroid_speed_ms, 5.0)  # 3-4-5
    assert np.allclose(d.centroid_x_rel_m, 3.0 * np.arange(30)) and np.allclose(d.n_drones, 4)


def test_descriptors_are_permutation_invariant() -> None:
    rng = np.random.default_rng(3)
    offsets = rng.normal(0.0, 30.0, (5, 2))
    pos = formation_track(offsets, 40, velocity=(2.0, -1.0), turn_dps=2.0)
    a = swarm_descriptors(np.arange(40), pos, np.zeros(2), 3)
    b = swarm_descriptors(np.arange(40), pos[rng.permutation(5)], np.zeros(2), 3)
    pd.testing.assert_frame_equal(a, b)


def test_rotation_rate_of_a_turning_line() -> None:
    line = np.array([[-60.0, 0.0], [-20.0, 0.0], [20.0, 0.0], [60.0, 0.0]])
    pos = formation_track(line, 120, turn_dps=3.0)  # 360° of axis travel: crosses 180° twice
    d = swarm_descriptors(np.arange(120), pos, np.zeros(2), 3)
    inner = d.rot_rate_dps.to_numpy()[5:-5]
    assert np.allclose(inner, 3.0, atol=0.2)
    assert np.all(np.abs(np.diff(d.axis_angle_deg.to_numpy())) < 10.0)  # unwrapped: no 180° jumps


def test_principal_axis_and_unwrap() -> None:
    north = np.array([[[0.0, -10.0], [0.0, 10.0]]])
    east = np.array([[[-10.0, 0.0], [10.0, 0.0]]])
    assert principal_axis_deg(north)[0] == pytest.approx(0.0, abs=1e-9)
    assert principal_axis_deg(east)[0] == pytest.approx(90.0)
    assert np.isnan(principal_axis_deg(np.array([[[1.0, 1.0], [np.nan, np.nan]]]))[0])
    u = unwrap_axis(np.array([170.0, 178.0, 4.0, np.nan, 12.0]))
    assert np.allclose(u[[0, 1, 2, 4]], [170.0, 178.0, 184.0, 192.0]) and np.isnan(u[3])


def test_detect_swarm_true_and_false() -> None:
    close = formation_track(SQUARE, 70)[..., :2]
    assert detect_swarm(close, 3, 300.0, 60) == (True, 70)
    wide = formation_track(SQUARE * 8.0, 70)[..., :2]  # diagonals 452 m
    assert detect_swarm(wide, 3, 300.0, 60)[0] is False
    short = close.copy()
    short[:, 50:] = np.nan  # together for 50 s only
    assert detect_swarm(short, 3, 300.0, 60) == (False, 50)
    assert detect_swarm(close[:2], 3, 300.0, 60)[0] is False  # two drones
    assert longest_run(np.array([1, 1, 0, 1, 1, 1, 0], dtype=bool)) == 3


def test_series_and_vector_shapes() -> None:
    pos = formation_track(SQUARE, 64, velocity=(1.0, 0.0), turn_dps=1.0)
    d = swarm_descriptors(np.arange(64), pos, np.zeros(2), 3)
    z = swarm_series(d)
    assert z.shape == (64, len(SERIES_COLUMNS)) and np.isfinite(z).all()
    # spread, quartiles and speed are constant here: z-normalized to zeros, never NaN
    assert np.allclose(z[:, 0], 0.0) and np.allclose(z[:, 5], 0.0)
    v = swarm_vector(z, 16)
    assert v.shape == (96,) and v.dtype == np.float32
    assert np.linalg.norm(v) == pytest.approx(1.0, abs=1e-5) or np.allclose(v, 0.0)
    assert swarm_vector(np.zeros((0, 6)), 16).shape == (96,)


def test_descriptors_skip_seconds_with_too_few_drones() -> None:
    pos = formation_track(SQUARE, 20)
    pos[1:, :5] = np.nan  # only one drone during the first 5 s
    d = swarm_descriptors(np.arange(20), pos, np.zeros(2), 3)
    assert d.t_s.tolist() == list(range(5, 20))


def test_drone_grid_resamples_every_track_on_one_grid() -> None:
    t0 = pd.Timestamp("2026-06-15 03:50:00")
    rows = []
    for k, tid in enumerate(["S-T1", "S-T2", "S-T3"]):
        for s in range(k, 30 + k):  # tracks start 0, 1 and 2 s apart
            ts = t0 + pd.Timedelta(seconds=s)
            rows.append({"track_id": tid, "ts": ts, "x_m": 10.0 * s + k, "y_m": 0.0,
                         "alt_m": 80.0, "quality": 1.0})  # fmt: skip
    t_s, tracks, pos = drone_grid(pd.DataFrame(rows), 10.0)
    assert tracks == ["S-T1", "S-T2", "S-T3"] and t_s.tolist() == list(range(32))
    assert pos.shape == (3, 32, 3)
    assert np.isnan(pos[2, 0, 0]) and np.isfinite(pos[2, 2, 0])  # T3's first point is at 2 s
    assert pos[0, 10, 0] == pytest.approx(100.0)
