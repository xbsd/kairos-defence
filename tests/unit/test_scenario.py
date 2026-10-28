"""Planted P1 flights and the live timing (SPEC §1.2, §6.4, §8.10, D-003, D-006)."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest
import shapely

from kairos_defense.sim.generate import simulate
from kairos_defense.sim.scenario import orbit_established_s, p1_plans
from kairos_defense.sim.world import nominal_launch


@pytest.fixture(scope="module")
def p1(cfg, world, cal):
    plans = p1_plans(cfg, world, 42)
    return {r.plan.key: r for r in simulate(plans, world, cal, 42)}


def test_six_planted_flights_as_configured(cfg, p1) -> None:
    assert list(p1) == [f.incident_id for f in cfg.scenario.p1_flights]
    for f in cfg.scenario.p1_flights:
        plan = p1[f.incident_id].plan
        assert plan.actor_id == "P1" and plan.actor_type == "prober"
        assert plan.installation_id == f.base
        assert plan.launch_local == f.start_local
        assert plan.time_warp == f.time_warp
        assert plan.incident_id == f.incident_id
        assert plan.target_kind == (f.target_override or "fuel_farm")
        assert plan.rf_family == "FAM-07" and plan.rid == "off"
        assert plan.pattern["type"] == "orbit" and plan.pattern["direction"] == "ccw"


def test_every_planted_flight_is_detected(p1) -> None:
    for key, r in p1.items():
        assert r.detected, key


def test_only_the_demo_flight_is_live(cfg, p1) -> None:
    live = [k for k, r in p1.items() if r.plan.status == "live"]
    assert live == [cfg.scenario.live_incident] == ["DEMO-BRAVO-0828"]


def test_live_flight_has_no_jitter(world, p1) -> None:
    plan = p1["DEMO-BRAVO-0828"].plan
    nominal = nominal_launch(world.sites["BRAVO"], "fuel_farm", 315.0, 2100.0)
    np.testing.assert_allclose(plan.launch_xy, nominal, atol=1e-6)
    assert plan.approach_bearing_deg == 315.0
    assert plan.pattern["radius_m"] == 180.0
    assert plan.pauses is False


@pytest.mark.parametrize("key", ["P1-BRAVO-251114", "P1-ALPHA-260303", "P1-DELTA-260419",
                                 "P1-ALPHA-260502", "DEMO-BRAVO-0828"])  # fmt: skip
def test_county_rd_12_within_250_m_of_launch(world, p1, key) -> None:
    road = world.road("County Rd 12")
    assert road.line.distance(shapely.Point(p1[key].plan.launch_xy)) <= 250.0


def test_charlie_keeps_its_nominal_launch(world, p1) -> None:
    plan = p1["P1-CHARLIE-260710"].plan
    nominal = nominal_launch(world.sites["CHARLIE"], "flight_line", 315.0, 2100.0)
    assert np.hypot(*(np.asarray(plan.launch_xy) - nominal)) <= 150.0 + 1e-6  # jitter only
    assert world.road("County Rd 12").line.distance(shapely.Point(plan.launch_xy)) > 500


def test_bravo_251114_outage(p1) -> None:
    r = p1["P1-BRAVO-251114"]
    assert r.plan.outage_s == (120.0, 260.0)
    t = r.hits.t_s
    assert not ((t >= 120) & (t <= 260)).any()
    assert (t < 120).any() and (t > 260).any()  # early, partial track


def test_live_launch_is_in_bravo_radar_shadow(world, p1) -> None:
    r = p1["DEMO-BRAVO-0828"]
    bravo = world.sites["BRAVO"]
    assert bravo.masked(np.asarray([r.plan.launch_xy]), np.array([150.0]))[0]
    rec = r.path.xyz[-1:, :2]
    assert bravo.masked(rec, np.array([100.0]))[0]  # the recovery zone is in the shadow too


def test_live_first_contact(cfg, world, p1) -> None:
    r = p1["DEMO-BRAVO-0828"]
    lo, hi = cfg.scenario.expectations.live_first_contact_local
    t0 = r.plan.launch_local + np.timedelta64(int(r.hits.t_s[0] * 1000), "ms").astype(object)
    assert lo <= t0 <= hi, t0
    assert lo == datetime(2026, 8, 28, 21, 39, 30)
    d = world.sites["BRAVO"].fence_distance(r.hits.xyz[:1, :2])[0]
    assert d <= 100.0
    true_d = world.sites["BRAVO"].fence_distance(r.path.xyz[int(r.hits.t_s[0]), None, :2])[0]
    assert true_d <= 50.0  # it appears where the ridge stops hiding it


def test_live_orbit_established(cfg, world, p1) -> None:
    r = p1["DEMO-BRAVO-0828"]
    lo, hi = cfg.scenario.expectations.live_orbit_established_s
    c = world.sites["BRAVO"].assets["fuel_farm"].centroid
    t0 = float(r.hits.t_s[0])
    est = orbit_established_s(r.path.t_s, r.path.xyz[:, :2], c, 180.0, after_s=t0)
    assert est is not None
    assert lo <= est - t0 <= hi, est - t0


def test_orbit_established_known_answer() -> None:
    t = np.arange(60.0)
    r = np.where(t < 20, 400.0, 182.0)
    r[25] = 230.0  # a wobble restarts the 10 s count
    xy = np.column_stack([r, np.zeros(60)])
    assert orbit_established_s(t, xy, (0, 0), 180.0) == 26.0
    assert orbit_established_s(t, xy, (0, 0), 180.0, after_s=40.0) == 40.0
    assert orbit_established_s(t[:15], xy[:15], (0, 0), 180.0) is None
