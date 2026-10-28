"""SPEC §9.4 signatures on synthetic tracks with known answers (D-024, D-047)."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.channels import track_features
from kairos_defense.features.signatures import (
    SIGNATURE_COLUMNS,
    SensorContext,
    signature,
    tod_minutes,
)
from tests.unit.synth import points, site

FARM = np.array([400.0, 300.0])


def approach_then_orbit(ccw: bool = True, laps: float = 2.0, alt0: float = 100.0) -> pd.DataFrame:
    """Inbound at 15 m/s from 1,500 m out on bearing 315 from the farm, then orbit 180 m."""
    b = np.radians(315.0)
    d = np.arange(1500.0, 180.0, -15.0)
    inbound = FARM + d[:, None] * np.array([np.sin(b), np.cos(b)])
    n_orbit = int(laps * 360 / 3.0)
    sgn = -1.0 if ccw else 1.0
    brg = np.radians(315.0 + sgn * 3.0 * np.arange(1, n_orbit + 1))
    orbit = FARM + 180.0 * np.stack([np.sin(brg), np.cos(brg)], axis=1)
    xy = np.vstack([inbound, orbit])
    alt = np.full(len(xy), 100.0)
    alt[0] = alt0
    return points(np.arange(len(xy)), xy[:, 0], xy[:, 1], alt=alt)


def sig(p: pd.DataFrame, cfg, ctx: SensorContext | None = None) -> dict:
    s = site()
    f, target = track_features(p, s, cfg.scoring)
    return signature(f, target, p.iloc[0], p.iloc[-1], s, ctx or SensorContext(),
                     {"track_id": "X-T1", "incident_id": "X"})  # fmt: skip


@pytest.mark.parametrize(("ccw", "expect"), [(True, "ccw"), (False, "cw")])
def test_orbit_signature(cfg, ccw: bool, expect: str) -> None:
    s = sig(approach_then_orbit(ccw=ccw), cfg)
    assert list(s) == SIGNATURE_COLUMNS
    assert s["target_asset_id"] == "TEST-fuel_farm"
    assert abs(s["approach_bearing_deg"] - 315.0) < 1.0
    assert abs(s["loiter_radius_m"] - 180.0) < 5.0
    assert s["loiter_dir"] == expect  # ccw = bearing from the target decreasing (D-024)
    assert s["dwell_s"] >= 240  # the whole orbit is within 1.5 x radius
    assert abs(s["alt_median_m"] - 100.0) < 1e-6


def test_hover_has_no_direction(cfg) -> None:
    rng = np.random.default_rng(0)
    n = 300
    xy = np.array([-300.0, -200.0]) + rng.normal(0, 5.0, size=(n, 2))  # over the hq
    s = sig(points(np.arange(n), xy[:, 0], xy[:, 1]), cfg)
    assert s["target_asset_id"] == "TEST-hq"
    assert s["loiter_dir"] == "none"


def test_short_pass_is_not_a_loiter(cfg) -> None:
    t = np.arange(120)
    s = sig(points(t, -2000.0 + 15.0 * t, np.full(120, 300.0)), cfg)
    assert s["loiter_dir"] == "none"


@pytest.mark.parametrize(
    ("utc", "offset", "minutes"),
    [(datetime(2026, 5, 4, 2, 0), -5, 1260), (datetime(2026, 5, 4, 6, 0), -5, 1500),
     (datetime(2026, 5, 4, 4, 59), -5, 1439), (datetime(2026, 5, 4, 5, 0), -5, 1440)],
)  # fmt: skip
def test_tod_wraps_past_midnight(utc, offset, minutes) -> None:
    assert tod_minutes(utc, offset) == minutes


def test_launch_and_recovery_rules(cfg) -> None:
    p = approach_then_orbit(alt0=20.0)
    p.loc[p.index[-1], "alt_m"] = 12.0
    s = sig(p, cfg)
    first, last = p.iloc[0], p.iloc[-1]
    assert np.isclose(s["launch_x_rel_m"], first.x_m - FARM[0])  # seen at takeoff (< 30 m)
    assert np.isclose(s["recovery_y_rel_m"], last.y_m - FARM[1])  # seen landing
    s = sig(approach_then_orbit(alt0=80.0), cfg)
    assert s["launch_x_rel_m"] is None and s["recovery_x_rel_m"] is None  # unknown (D-003)


def test_remote_id_operator_is_the_launch_when_serial_is_stable(cfg) -> None:
    ctx = SensorContext("FAM-02", ("SN-0000000000000001",), (1000.0, 1300.0))
    s = sig(approach_then_orbit(alt0=80.0), cfg, ctx)
    assert (s["launch_x_rel_m"], s["launch_y_rel_m"]) == (600.0, 1000.0)
    assert s["rid_present"] and s["rid_serial"] == "SN-0000000000000001"
    assert s["rf_family"] == "FAM-02"
    two = SensorContext("FAM-02", ("SN-A", "SN-B"), (1000.0, 1300.0))  # not stable
    s = sig(approach_then_orbit(alt0=80.0), cfg, two)
    assert s["launch_x_rel_m"] is None and s["rid_serial"] == "SN-A"
    s = sig(approach_then_orbit(), cfg)
    assert s["rf_family"] == "unknown" and not s["rid_present"] and s["rid_serial"] is None


def test_alt_median_skips_takeoff_and_landing(cfg) -> None:
    p = approach_then_orbit()
    k = 30
    p.loc[: k - 1, "alt_m"] = np.linspace(15, 99, k)
    p.loc[len(p) - k :, "alt_m"] = np.linspace(99, 15, k)
    p.loc[k : len(p) - k - 1, "alt_m"] = 110.0
    assert sig(p, cfg)["alt_median_m"] == pytest.approx(110.0, abs=1.0)
