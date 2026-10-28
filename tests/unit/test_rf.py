"""RF model (SPEC §8.6): family per actor, band, rate, range, mask, bearing noise and SNR."""

from __future__ import annotations

import numpy as np
import pytest

from kairos_defense import geo
from kairos_defense.sim.kinematics import FlightPath
from kairos_defense.sim.sensors import SNR_REF_DB, rf_band, rf_track

N_S = 4000


def _static(xy, alt: float, n: int = N_S) -> FlightPath:
    xyz = np.tile([xy[0], xy[1], alt], (n, 1))
    return FlightPath("static", np.arange(n, dtype=np.float64), xyz, np.zeros(n, np.int8))


def _around_rf(site, bearing: float, dist: float, alt: float = 100.0, n: int = N_S):
    return _static(geo.destination(site.sensors["rf"].xy, bearing, dist), alt, n)


@pytest.mark.parametrize(
    ("family", "band"),
    [("FAM-01", "2.4GHz"), ("FAM-07", "2.4GHz"), ("FAM-11", "5.8GHz"), ("FAM-15", "5.8GHz"),
     ("FAM-21", "900MHz"), ("FAM-30", "900MHz"), ("FAM-31", "900MHz")],
)  # fmt: skip
def test_rf_band_from_family(family: str, band: str) -> None:
    assert rf_band(family) == band


def test_rf_unknown_family_is_an_error() -> None:
    with pytest.raises(ValueError):
        rf_band("FAM-91")


def test_rf_family_per_actor(cfg, world, sample) -> None:
    expected = {p.id: p.rf_family for p in cfg.actors.probers}
    expected |= {c.id: c.rf_family for c in cfg.actors.copycats}
    seen = set()
    for plan, path in zip(sample.plans, sample.paths, strict=True):
        hits = rf_track(path, world.sites[plan.installation_id], plan.rf_family,
                        np.random.default_rng(3))  # fmt: skip
        assert len(hits) > 0, plan.key
        if plan.actor_type == "hobbyist":
            assert hits.family in cfg.actors.hobbyists.rf_families
        else:
            assert hits.family == expected[plan.actor_id], plan.key
            seen.add(plan.actor_id)
        assert hits.band == rf_band(hits.family)
    assert seen == set(expected)
    assert expected["P1"] == expected["P3"] == "FAM-07"  # RF alone must not decide a match


def test_rf_rate_while_airborne_and_in_range(world) -> None:
    site = world.sites["GOLF"]
    rate = site.sensors["rf"].params["rate_hz"]
    hits = rf_track(_around_rf(site, 30.0, 2000.0), site, "FAM-03", np.random.default_rng(0))
    assert len(hits) == N_S * rate
    np.testing.assert_allclose(np.diff(hits.t_s), 1.0 / rate)
    ground = rf_track(_around_rf(site, 30.0, 2000.0, alt=0.0), site, "FAM-03",
                      np.random.default_rng(0))  # fmt: skip
    assert len(ground) == 0  # only while airborne
    far = rf_track(_around_rf(site, 30.0, 4050.0, alt=10.0), site, "FAM-03",
                   np.random.default_rng(0))  # fmt: skip
    assert len(far) == 0  # beyond 4 km (slant)


def test_rf_bearing_noise(world) -> None:
    site = world.sites["KILO"]
    hits = rf_track(_around_rf(site, 60.0, 2000.0), site, "FAM-15", np.random.default_rng(1))
    err = geo.wrap180(hits.bearing_deg - 60.0)
    assert float(np.mean(err)) == pytest.approx(0.0, abs=0.3)
    sigma = site.sensors["rf"].params["bearing_sigma_deg"]
    assert float(np.std(err)) == pytest.approx(sigma, rel=0.08)
    assert ((hits.bearing_deg >= 0.0) & (hits.bearing_deg < 360.0)).all()


def test_rf_snr_falls_with_range(world) -> None:
    site = world.sites["ECHO"]
    snr = []
    for d in (100.0, 1000.0, 3500.0):
        h = rf_track(_around_rf(site, 200.0, d, alt=1.0), site, "FAM-30", np.random.default_rng(2))
        snr.append(float(np.mean(h.snr_db)))
    assert snr[0] == pytest.approx(SNR_REF_DB, abs=0.3)
    assert snr[1] == pytest.approx(SNR_REF_DB - 20.0, abs=0.3)  # 20 dB per decade
    assert snr[0] > snr[1] > snr[2]


def test_rf_honors_the_terrain_mask(world) -> None:
    bravo = world.sites["BRAVO"]
    xy = geo.destination(bravo.origin, 330.0, 2000.0)  # northwest, beyond the fence
    low = rf_track(_static(xy, 120.0), bravo, "FAM-07", np.random.default_rng(0))
    high = rf_track(_static(xy, 250.0), bravo, "FAM-07", np.random.default_rng(0))
    assert len(low) == 0 and len(high) > 0


def test_rf_same_stream_same_hits(world) -> None:
    site = world.sites["DELTA"]
    a = rf_track(_around_rf(site, 10.0, 900.0), site, "FAM-07", np.random.default_rng(9))
    b = rf_track(_around_rf(site, 10.0, 900.0), site, "FAM-07", np.random.default_rng(9))
    np.testing.assert_array_equal(a.bearing_deg, b.bearing_deg)
    np.testing.assert_array_equal(a.snr_db, b.snr_db)
