"""SPEC §9.2-§9.3: target choice, target-relative columns and normalized channels."""

from __future__ import annotations

import numpy as np
import pandas as pd

from kairos_defense.features.channels import (
    add_target_columns,
    channel_matrix,
    choose_target,
    in_flight_mask,
    normalize,
    track_features,
)
from kairos_defense.features.resample import resample
from tests.unit.synth import circle, points, site, straight


def _with_inbound(orbit_center, radius: float):
    """Fast straight inbound leg then a slow orbit around ``orbit_center``."""
    inbound = straight(60, speed=15.0, bearing_deg=135.0)  # from (0, 0) toward the southeast
    orbit = circle(300, radius=radius, rate_dps=3.0, center=orbit_center)
    orbit["ts"] = (
        orbit["ts"] + (inbound["ts"].iloc[-1] - orbit["ts"].iloc[0]) + pd.Timedelta(1, "s")
    )
    return pd.concat([inbound, orbit], ignore_index=True)


def test_orbit_picks_its_asset(cfg) -> None:
    s = site()
    _, target = track_features(_with_inbound((400.0, 300.0), 180.0), s, cfg.scoring)
    assert target.asset_id == "TEST-fuel_farm"
    _, t2 = track_features(_with_inbound((-300.0, -200.0), 150.0), s, cfg.scoring)
    assert t2.asset_id == "TEST-hq"


def test_perimeter_run_picks_the_fence() -> None:
    s = site(fence_half=1000.0)
    t = np.arange(400)
    x = -1200.0 + 6.0 * t  # 200 m outside the north fence, running east
    f = resample(points(t, x, np.full(400, 1200.0)))
    target = choose_target(s, f[["x_m", "y_m"]].to_numpy(), f.speed_ms.to_numpy(), f.alt_m)
    assert target.kind == "fence"
    out = add_target_columns(f, target)
    along = out.x_m.abs() <= 1000.0  # beyond the corners the nearest fence point is the corner
    assert np.allclose(out.dist_target_m[along], 200.0, atol=1e-6)


def test_target_columns() -> None:
    s = site()
    farm = s.target("TEST-fuel_farm")
    f = pd.DataFrame({"x_m": [400.0, 400.0, 400.0], "y_m": [300.0, 400.0, 500.0]})
    out = add_target_columns(f, farm)
    assert np.allclose(out.x_rel_m, 0.0)
    assert np.allclose(out.y_rel_m.iloc[1], 100.0)
    assert out.dist_target_m.iloc[0] == 0.0  # inside the polygon
    assert np.isclose(out.dist_target_m.iloc[1], 75.0)  # 100 m from the centroid, 25 m half-size
    assert np.allclose(out.bearing_rel_deg.iloc[1:], 0.0)  # due north of the target
    fence = s.target("TEST-fence")
    assert np.allclose(fence.distance(np.array([[0.0, 0.0], [0.0, 1100.0]])), [1000.0, 100.0])


def test_fence_target_centroid_and_radius() -> None:
    s = site(fence_half=1000.0)
    assert s.targets[-1].kind == "fence"
    assert np.isclose(s.target("TEST-fuel_farm").radius_m, np.sqrt(2500 / np.pi))


def test_normalize_known_answer() -> None:
    m = np.array([[1.0, 5.0, np.nan], [2.0, 5.0, np.nan], [3.0, 5.0, np.nan]])
    z = normalize(m, [2.0, 1.0, 1.0])
    sd = np.std([1.0, 2.0, 3.0])
    assert np.allclose(z[:, 0], 2.0 * (np.array([1, 2, 3]) - 2.0) / sd)
    assert np.allclose(z[:, 1], 0.0)  # constant channel: σ floor, no blow-up
    assert np.isnan(z[:, 2]).all()


def test_channel_order_follows_config(cfg) -> None:
    sc = cfg.scoring
    f, _ = track_features(_with_inbound((400.0, 300.0), 180.0), site(), sc)
    m = channel_matrix(f, sc)
    assert m.shape == (len(f), 5)
    assert np.array_equal(m[:, 2], f.dist_target_m.to_numpy(), equal_nan=True)


def test_in_flight_mask_drops_takeoff_and_landing() -> None:
    alt = np.r_[np.linspace(10, 100, 30), np.full(200, 100.0), np.linspace(100, 10, 30)]
    m = in_flight_mask(alt)
    assert not m[:20].any() and not m[-20:].any() and m[30:230].all()
    dips = np.r_[np.full(50, 300.0), np.full(10, 80.0), np.full(50, 300.0)]  # P6-style dip
    assert in_flight_mask(dips).all()


def test_takeoff_far_away_does_not_steal_the_target(cfg) -> None:
    """D-046: slow takeoff and landing 2 km out must not make the fence the target (P1 at ALPHA)."""
    t = np.arange(40)
    climb = points(t, np.full(40, -1500.0), np.full(40, 1500.0), alt=15 + 2.5 * t)
    track = _with_inbound((400.0, 300.0), 180.0)
    track["ts"] = track["ts"] + pd.Timedelta(40, "s")
    land = climb.iloc[::-1].reset_index(drop=True)
    land["ts"] = track["ts"].iloc[-1] + pd.to_timedelta(np.arange(1, 41), unit="s")
    _, target = track_features(
        pd.concat([climb, track, land], ignore_index=True), site(), cfg.scoring
    )
    assert target.asset_id == "TEST-fuel_farm"
