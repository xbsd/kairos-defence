"""Actor scheduling and per-flight variation (SPEC §6.3, §8.2, §8.5, D-005)."""

from __future__ import annotations

import dataclasses
from collections import Counter

import numpy as np
import pytest
import shapely

from kairos_defense.sim.actors import actor_specs, schedule, schedule_actor
from kairos_defense.sim.calendar import hhmm_to_night_min


@pytest.fixture(scope="module")
def plans(cfg, world, cal):
    return schedule(cfg, world, cal, 42)


def _by_actor(plans) -> dict[str, list]:
    out: dict[str, list] = {}
    for p in plans:
        if p.actor_type != "hobbyist":
            out.setdefault(p.actor_id, []).append(p)
    return out


def test_counts_per_actor(cfg, plans) -> None:
    by = _by_actor(plans)
    expected = {p.id: p.flights for p in cfg.actors.probers if p.flights != "planted_only"}
    expected |= {c.id: c.flights for c in cfg.actors.copycats}
    assert {a: len(v) for a, v in by.items()} == expected
    assert "P1" not in by  # every P1 flight is planted (scenario.py)
    n_hob = sum(p.actor_type == "hobbyist" for p in plans)
    assert n_hob == pytest.approx(0.27 * 549 * 12, rel=0.08)


def test_keys_unique(plans) -> None:
    keys = [p.key for p in plans]
    assert len(keys) == len(set(keys))


def test_bases_and_time_windows(cfg, cal, plans) -> None:
    specs = {s.actor_id: s for s in actor_specs(cfg)}
    for actor, ps in _by_actor(plans).items():
        spec = specs[actor]
        lo = hhmm_to_night_min(spec.time_local[0], cal.night_start)
        hi = hhmm_to_night_min(spec.time_local[1], cal.night_start)
        for p in ps:
            assert p.installation_id in spec.bases
            m = (p.launch_local - cal.night_start_local(p.night)).total_seconds() / 60
            assert lo <= m <= hi, (actor, p.launch_local)
    late = [p for p in _by_actor(plans)["P6"]]  # 01:00-03:00: the morning after the night's date
    assert all(p.launch_local.date() > p.night for p in late)
    for p in plans:
        if p.actor_type == "hobbyist":
            m = (p.launch_local - cal.night_start_local(p.night)).total_seconds() / 60
            assert 0 <= m <= 240  # 19:00-23:00


def test_time_warp_ranges(plans) -> None:
    for p in plans:
        if p.actor_type == "hobbyist":
            assert p.time_warp == 1.0
        else:
            assert 0.7 <= p.time_warp <= 1.4


def test_spread_uniformly_by_month(plans) -> None:
    for actor, ps in _by_actor(plans).items():
        months = Counter((p.night.year, p.night.month) for p in ps)
        assert max(months.values()) <= 2, actor  # ≤ 16 flights over 18 months


def test_vip_nights_weighted_three_times(cfg, world, cal) -> None:
    spec = next(s for s in actor_specs(cfg) if s.actor_id == "P2")
    spec = dataclasses.replace(spec, flights=1800, bases=["DELTA"])
    ps = schedule_actor(cfg, world, cal, 11, spec)
    vip = cal.vip_nights["DELTA"]
    on_vip = np.mean([vip[cal.night_index(p.night)] for p in ps])
    v = vip.mean()
    assert on_vip == pytest.approx(3 * v / (3 * v + 1 - v), abs=0.03)


def test_launch_points_outside_the_fence(world, plans) -> None:
    for p in plans:
        fence = world.sites[p.installation_id].fence
        d = fence.distance(shapely.Point(p.launch_xy))
        assert d >= 300.0 - 1e-6 and not fence.contains(shapely.Point(p.launch_xy)), p.key


def test_pushed_out_launches(world, plans) -> None:
    c2 = [p for p in plans if p.actor_id == "C2"]
    for p in c2:  # nominal launch is inside the fence: pushed out along its bearing (D-005)
        fence = world.sites[p.installation_id].fence
        assert fence.distance(shapely.Point(p.launch_xy)) == pytest.approx(300.0, abs=0.01)


def test_hobbyists_launch_from_their_park(world, plans) -> None:
    for p in plans:
        if p.actor_type == "hobbyist":
            park = world.park(world.sites[p.installation_id].park_id)
            assert np.hypot(*(np.asarray(p.launch_xy) - park.center)) <= park.radius_m + 1e-6
            assert p.pattern["type"] == "random_walk"
            assert 180 <= p.pattern["duration_s"] <= 720
            assert 30 <= p.altitude_m <= 120 and 4 <= p.cruise_ms <= 12


def test_cross_fence_share(plans) -> None:
    hob = [p for p in plans if p.actor_type == "hobbyist"]
    share = np.mean([p.pattern["cross_fence"] for p in hob])
    assert share == pytest.approx(0.3, abs=0.04)


def test_per_flight_variation(cfg, plans) -> None:
    by = _by_actor(plans)
    for p in by["C1"]:  # copycat: P1's orbit, its own radius range, launch side and RF
        assert 170 <= p.pattern["radius_m"] <= 190
        assert p.pattern["direction"] == "ccw"
        assert 90 <= p.altitude_m <= 120 and p.cruise_ms == 15
        assert abs(((p.approach_bearing_deg - 120 + 180) % 360) - 180) <= 10
        assert p.rf_family == "FAM-02"
    for p in by["P3"] + by["C2"]:
        assert 120 * 0.92 <= p.pattern["lobe_radius_m"] <= 120 * 1.08
        assert p.pattern["loops"] in (2, 3)
    for p in by["P2"]:
        assert p.pattern["legs"] in (4, 5, 6)
        assert abs(((p.approach_bearing_deg - 200 + 180) % 360) - 180) <= 10
    for p in by["P4"]:
        assert 0.4 <= p.pattern["fraction"] <= 0.7
    for p in by["P5"]:
        assert 240 <= p.pattern["dwell_s"] <= 360
    for actor, ps in by.items():
        r = 120.0 if actor == "P1" else 300.0
        for p in ps:
            assert np.hypot(*np.subtract(p.recovery_xy, p.launch_xy)) <= r + 1e-9
