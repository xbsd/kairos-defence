"""SPEC §9.1 resampling: known answers on synthetic straight lines and circles."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.resample import FEATURE_COLUMNS, resample
from tests.unit.synth import circle, points, straight


def test_straight_line_speed_heading_turn() -> None:
    f = resample(straight(121, speed=12.0, bearing_deg=45.0))
    assert list(f.columns) == FEATURE_COLUMNS
    assert len(f) == 121 and f.t_s.tolist() == list(range(121))
    inner = f.iloc[3:-3]
    assert np.allclose(inner.speed_ms, 12.0, atol=1e-9)
    assert np.allclose(inner.heading_deg, 45.0, atol=1e-9)
    assert np.allclose(inner.turn_rate_dps, 0.0, atol=1e-9)
    assert np.allclose(inner.vspeed_ms, 0.0, atol=1e-9)
    assert not f.in_gap.any()


@pytest.mark.parametrize(("ccw", "sign"), [(True, -1.0), (False, 1.0)])
def test_circle_speed_and_turn_rate(ccw: bool, sign: float) -> None:
    f = resample(circle(361, radius=180.0, rate_dps=3.0, ccw=ccw))
    inner = f.iloc[5:-5]
    assert np.allclose(inner.speed_ms, 180.0 * np.radians(3.0), rtol=0.01)
    # the per-axis 3 s median flattens the circle a little where x or y peaks (±0.25 deg/s)
    assert np.allclose(inner.turn_rate_dps, sign * 3.0, atol=0.3)
    assert np.isclose(inner.turn_rate_dps.mean(), sign * 3.0, atol=0.01)
    # heading is perpendicular to the radius: bearing - 90 for ccw, + 90 for cw
    brg = np.degrees(np.arctan2(inner.x_m, inner.y_m)) % 360
    expect = (brg + sign * 90.0) % 360
    assert np.allclose(((inner.heading_deg - expect + 180) % 360) - 180, 0, atol=1.0)


def test_climb_rate() -> None:
    t = np.arange(60)
    f = resample(points(t, t * 5.0, np.zeros(60), alt=20 + 2.5 * t))
    assert np.allclose(f.vspeed_ms.iloc[3:-3], 2.5, atol=1e-9)


def test_duplicates_keep_highest_quality() -> None:
    p = points([0, 1, 1, 2, 3], [0, 10, 999, 20, 30], [0, 0, 0, 0, 0],
               quality=[0.9, 0.5, 0.95, 0.9, 0.9])  # fmt: skip
    f = resample(p)
    assert len(f) == 4
    # the smoothed value at t=1 is pulled toward 999 only if the duplicate won
    assert f.x_m.iloc[1] > 100


def test_short_gaps_are_interpolated_long_gaps_marked() -> None:
    t = np.r_[np.arange(0, 21), np.arange(29, 41)]  # 8 s gap: interpolate
    f = resample(points(t, t * 10.0, np.zeros(len(t))), max_interp_gap_s=10)
    assert len(f) == 41 and not f.in_gap.any()
    assert np.allclose(f.x_m.iloc[22:28], np.arange(22, 28) * 10.0)

    t = np.r_[np.arange(0, 21), np.arange(35, 51)]  # 14 s gap: mark
    f = resample(points(t, t * 10.0, np.zeros(len(t))), max_interp_gap_s=10)
    gap = f.in_gap.to_numpy()
    assert gap[21:35].all() and not gap[:21].any() and not gap[35:].any()
    assert f.loc[gap, ["x_m", "speed_ms", "heading_deg", "turn_rate_dps"]].isna().all().all()
    assert f.loc[~gap, "speed_ms"].notna().all()


def test_smoothing_does_not_cross_gaps() -> None:
    t = np.r_[np.arange(0, 21), np.arange(40, 61)]
    x = np.r_[np.zeros(21), np.full(21, 5000.0)]
    f = resample(points(t, x, np.zeros(len(t))))
    assert np.allclose(f.x_m.iloc[:21], 0.0)
    assert np.allclose(f.x_m.iloc[40:], 5000.0)
    assert np.allclose(f.speed_ms.dropna(), 0.0)


def test_fractional_timestamps_go_to_whole_seconds() -> None:
    t = np.arange(0, 30) + 0.5
    f = resample(points(t, t * 4.0, np.zeros(30)))
    assert f.t_s.iloc[0] == 0 and len(f) == 29
    first = pd.Timestamp(f.ts.iloc[0])
    assert first.microsecond == 0 and first.second == 1
    assert np.allclose(f.x_m.iloc[3:-3], (np.arange(3, 26) + 1.0) * 4.0)


def test_spike_is_suppressed() -> None:
    x = np.arange(40) * 10.0
    x[20] += 300.0  # one radar outlier
    f = resample(points(np.arange(40), x, np.zeros(40)))
    assert abs(f.x_m.iloc[20] - 200.0) < 10.0  # a 300 m outlier moves the track < 10 m


def test_empty_and_single_point() -> None:
    assert len(resample(points([], [], []))) == 0
    f = resample(points([0], [1.0], [2.0]))
    assert len(f) == 1 and np.isnan(f.speed_ms.iloc[0])


def test_epoch_ms() -> None:
    from datetime import datetime

    from kairos_defense.features.resample import epoch_ms

    assert epoch_ms(datetime(2025, 3, 7, 1, 17, 34)) == 1741310254000
    assert epoch_ms(pd.Timestamp("1970-01-01 00:00:01.5")) == 1500
