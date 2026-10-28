"""Radar model (SPEC §8.6): detection vs range, noise, minimum altitude, outages, dropouts, mask."""

from __future__ import annotations

import numpy as np
import pytest

from kairos_defense import geo
from kairos_defense.sim.kinematics import FlightPath
from kairos_defense.sim.sensors import DROPOUT_ENTER_P, DROPOUT_MEAN_S, dropout_up, radar_track

N_S = 20_000


def _static(site, bearing: float, dist: float, alt: float, n: int = N_S) -> FlightPath:
    xy = geo.destination(site.origin, bearing, dist)
    xyz = np.tile([xy[0], xy[1], alt], (n, 1))
    return FlightPath("static", np.arange(n, dtype=np.float64), xyz, np.zeros(n, np.int8))


def _p(site, slant: float) -> float:
    prm = site.sensors["radar"].params
    return prm["p_detect_near"] + (prm["p_detect_far"] - prm["p_detect_near"]) * slant / 3500.0


def test_dropout_chain() -> None:
    up = dropout_up(400_000, np.random.default_rng(0))
    stationary = DROPOUT_ENTER_P / (DROPOUT_ENTER_P + 1.0 / DROPOUT_MEAN_S)
    assert (~up).mean() == pytest.approx(stationary, abs=0.01)  # ≈ 15%
    starts = np.flatnonzero(np.diff(up.astype(int)) == -1)
    ends = np.flatnonzero(np.diff(up.astype(int)) == 1)
    lengths = ends[: len(starts)] - starts[: len(ends)]
    assert lengths.mean() == pytest.approx(DROPOUT_MEAN_S, rel=0.05)
    assert up[0]


@pytest.mark.parametrize("dist", [500.0, 1800.0, 3200.0])
def test_detection_rate_falls_with_range(world, dist: float) -> None:
    site = world.sites["GOLF"]
    hits = radar_track(_static(site, 45.0, dist, 100.0), site, np.random.default_rng(1))
    slant = np.hypot(dist, 100.0)
    up = 1.0 - DROPOUT_ENTER_P / (DROPOUT_ENTER_P + 1.0 / DROPOUT_MEAN_S)
    assert len(hits) / N_S == pytest.approx(_p(site, slant) * up, abs=0.02)
    np.testing.assert_allclose(hits.quality, round(_p(site, slant), 4))


def test_position_noise_grows_with_range(world) -> None:
    site = world.sites["GOLF"]
    for dist in (500.0, 3000.0):
        path = _static(site, 200.0, dist, 120.0)
        hits = radar_track(path, site, np.random.default_rng(2))
        err = hits.xyz - path.xyz[0]
        sigma = 8.0 + 0.004 * np.hypot(dist, 120.0)
        assert err[:, 0].std() == pytest.approx(sigma, rel=0.05)
        assert err[:, 1].std() == pytest.approx(sigma, rel=0.05)
        assert err[:, 2].std() == pytest.approx(5.0, rel=0.05)


def test_nothing_below_min_altitude_or_out_of_range(world) -> None:
    site = world.sites["GOLF"]
    low = _static(site, 0.0, 1000.0, 10.0, 2000)
    far = _static(site, 0.0, 3600.0, 100.0, 2000)
    assert len(radar_track(low, site, np.random.default_rng(3))) == 0
    assert len(radar_track(far, site, np.random.default_rng(3))) == 0


def test_planted_outage(world) -> None:
    site = world.sites["GOLF"]
    hits = radar_track(
        _static(site, 90.0, 800.0, 100.0, 600), site, np.random.default_rng(4), (120, 260)
    )
    assert not ((hits.t_s >= 120) & (hits.t_s <= 260)).any()
    assert ((hits.t_s < 120) | (hits.t_s > 260)).sum() > 300


def test_terrain_mask_hides_low_targets(world) -> None:
    bravo = world.sites["BRAVO"]
    low = radar_track(_static(bravo, 330.0, 2000.0, 100.0, 2000), bravo, np.random.default_rng(5))
    high = radar_track(_static(bravo, 330.0, 2000.0, 250.0, 2000), bravo, np.random.default_rng(5))
    east = radar_track(_static(bravo, 90.0, 2000.0, 100.0, 2000), bravo, np.random.default_rng(5))
    assert len(low) == 0
    assert len(high) > 1000 and len(east) > 1000


def test_same_stream_same_hits(world) -> None:
    site = world.sites["HOTEL"]
    path = _static(site, 10.0, 1500.0, 80.0, 1000)
    a = radar_track(path, site, np.random.default_rng(6))
    b = radar_track(path, site, np.random.default_rng(6))
    np.testing.assert_array_equal(a.t_s, b.t_s)
    np.testing.assert_array_equal(a.xyz, b.xyz)
