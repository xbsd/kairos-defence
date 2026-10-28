"""Calendar (SPEC §8.2): nights, weather, base events and public events."""

from __future__ import annotations

from datetime import date, datetime, time

import numpy as np
import pandas as pd
import pytest

from kairos_defense.sim.calendar import (
    Calendar,
    build_calendar,
    hhmm_to_night_min,
    local_to_utc_ms,
    utc_ms_to_local,
)


def test_549_nights(cal: Calendar) -> None:
    assert len(cal.nights) == 549
    assert cal.nights[0] == date(2025, 3, 1)
    assert cal.nights[-1] == date(2026, 8, 31)
    assert cal.night_start == time(19, 0)
    assert cal.night_len_min == 480


def test_time_helpers() -> None:
    t = datetime(2026, 8, 28, 21, 38, 45)
    ms = local_to_utc_ms(t, -5)
    assert ms == int(pd.Timestamp("2026-08-29T02:38:45").value // 1_000_000)
    assert utc_ms_to_local(ms, -5) == t
    start = time(19, 0)
    assert hhmm_to_night_min("19:00", start) == 0
    assert hhmm_to_night_min("23:00", start) == 240
    assert hhmm_to_night_min("01:00", start) == 360
    assert hhmm_to_night_min("03:00", start) == 480


def test_weather_series(cal: Calendar) -> None:
    wx = cal.weather
    assert len(wx) == 3 * 549 * 9  # hourly from 19:00 to 03:00 local
    assert wx.wind_ms.mean() == pytest.approx(5.0, abs=0.15)
    assert (wx.wind_ms >= 0).all()
    assert wx.wind_dir_deg.between(0, 360, inclusive="left").all()
    assert wx.visibility_km.between(2, 15).all()
    first = wx[wx.region_id == "COASTAL"].ts.iloc[0]  # 19:00 local at UTC-5
    assert first == pd.Timestamp("2025-03-02T00:00:00")
    # direction is a slow random walk, not white noise
    steps = np.abs(((np.diff(cal.wind_dir_deg["PLAINS"], axis=1) + 180) % 360) - 180)
    assert np.median(steps) < 15


def test_wind_is_hour_to_hour_correlated(cal: Calendar) -> None:
    sp = cal.wind_ms["COASTAL"]
    r = np.corrcoef(sp[:, :-1].ravel(), sp[:, 1:].ravel())[0, 1]
    assert 0.5 < r < 0.85


def test_wind_vector_blows_downwind(cal: Calendar) -> None:
    i = int(np.argmax(cal.wind_ms["DESERT"][:, 0]))
    v = cal.wind_vectors("DESERT", np.array([i]), np.array([0]))[0]
    speed, frm = cal.wind_ms["DESERT"][i, 0], cal.wind_dir_deg["DESERT"][i, 0]
    assert np.hypot(*v) == pytest.approx(speed)
    to = np.degrees(np.arctan2(v[0], v[1])) % 360
    assert ((to - frm) % 360) == pytest.approx(180.0, abs=1e-6)
    # as-of semantics: hours past the end hold the last value
    late = cal.wind_vectors("DESERT", np.array([i]), np.array([99]))[0]
    np.testing.assert_allclose(late, cal.wind_vectors("DESERT", np.array([i]), np.array([8]))[0])


def test_weather_is_seeded(cfg, world, cal: Calendar) -> None:
    again = build_calendar(cfg, world, 42)
    other = build_calendar(cfg, world, 43)
    pd.testing.assert_frame_equal(cal.weather, again.weather)
    assert not cal.weather.wind_ms.equals(other.weather.wind_ms)


def test_shift_changes_daily_at_2200(cal: Calendar, world) -> None:
    sc = cal.base_events[cal.base_events.kind == "shift_change"]
    assert len(sc) == 12 * 549
    for sid, site in world.sites.items():
        local = sc[sc.installation_id == sid].start_ts + pd.Timedelta(hours=site.utc_offset_hours)
        assert (local.dt.time == time(22, 0)).all()


def test_exercise_and_vip_counts(cal: Calendar) -> None:
    be = cal.base_events
    n_ex = (be.kind == "exercise").sum()
    n_vip = (be.kind == "vip_visit").sum()
    assert n_ex == pytest.approx(12 * 549 / 7, rel=0.12)  # about weekly
    assert n_vip == pytest.approx(12 * 549 / 30, rel=0.25)  # about monthly
    dur_h = (be.end_ts - be.start_ts).dt.total_seconds() / 3600
    assert dur_h[be.kind == "exercise"].between(2, 6).all()
    assert dur_h[be.kind == "vip_visit"].between(4, 8).all()
    for sid, flags in cal.vip_nights.items():
        assert flags.sum() == ((be.kind == "vip_visit") & (be.installation_id == sid)).sum()


def test_public_events_on_weekends_in_public_parks(cal: Calendar, world) -> None:
    pe = cal.public_events
    assert 150 < len(pe) < 400
    for _, ev in pe.iterrows():
        off = world.regions[ev.region_id]
        night = (ev.start_ts + pd.Timedelta(hours=off)).date()
        assert night.weekday() in (4, 5)
        parks = world.public_parks(ev.region_id)
        d = [np.hypot(ev.x_m - p.center[0], ev.y_m - p.center[1]) - p.radius_m for p in parks]
        assert min(d) <= 1e-6
    i = cal.night_index(date(2025, 3, 7))
    near = cal.public_events_near("COASTAL", i, (25800, -1200), 5000)
    far = cal.public_events_near("COASTAL", i, (-90000, 0), 5000)
    assert len(far) == 0
    assert len(near) == len(cal.public_xy.get(("COASTAL", i), np.zeros((0, 2))))
