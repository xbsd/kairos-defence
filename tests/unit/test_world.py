"""World build (SPEC §8.1, D-005, D-006, D-007, D-003 terrain mask)."""

from __future__ import annotations

import itertools

import numpy as np
import pytest
import shapely

from kairos_defense import geo
from kairos_defense.sim.world import (
    ROAD_SPACING_M,
    build_world,
    nominal_launch,
    push_out,
    ray_exit_distance,
    snap_to_road,
)
from kairos_defense.store.ddl import RAW_COLUMNS


def test_twelve_sites_three_regions(world) -> None:
    assert len(world.sites) == 12
    assert set(world.regions) == {"COASTAL", "PLAINS", "DESERT"}


def test_rotation_is_clockwise(world) -> None:
    bravo = world.sites["BRAVO"]  # rotation 12
    corner = np.asarray(bravo.fence.exterior.coords[2])  # template (1300, 1000)
    expected = geo.wrap360(np.degrees(np.arctan2(1300, 1000)) + 12.0)
    assert float(geo.bearing(bravo.origin, corner)) == pytest.approx(float(expected))
    charlie = world.sites["CHARLIE"]  # rotation -8
    corner = np.asarray(charlie.fence.exterior.coords[2])
    expected = geo.wrap360(np.degrees(np.arctan2(1300, 1000)) - 8.0)
    assert float(geo.bearing(charlie.origin, corner)) == pytest.approx(float(expected))


def test_sensor_positions(world) -> None:
    for site in world.sites.values():
        np.testing.assert_allclose(site.sensors["radar"].xy, site.origin, atol=1e-9)
        rf = geo.installation_to_region((200, 150), site.origin, site.rotation_deg)
        np.testing.assert_allclose(site.sensors["rf"].xy, rf, atol=1e-9)
        assert site.sensors["radar"].range_m == 3500
        assert site.sensors["radar"].sensor_id == f"{site.installation_id}-RADAR-1"


def test_asset_jitter_is_seeded_and_small(cfg, world) -> None:
    again = build_world(cfg, 42)
    other = build_world(cfg, 7)
    for sid, site in world.sites.items():
        for kind, a in site.assets.items():
            np.testing.assert_array_equal(a.centroid, again.sites[sid].assets[kind].centroid)
            tpl = cfg.world.installation_template.assets[kind].center
            nominal = geo.installation_to_region(tpl, site.origin, site.rotation_deg)
            assert np.hypot(*(a.centroid - nominal)) < 5 * cfg.world.installation_template.jitter_m
            assert a.polygon.contains(shapely.Point(a.centroid))
    a = world.sites["ALPHA"].assets["fuel_farm"].centroid
    assert not np.array_equal(a, other.sites["ALPHA"].assets["fuel_farm"].centroid)


def test_each_site_has_a_launch_park_22_km_out(world) -> None:
    for site in world.sites.values():
        park = world.park(site.park_id)
        assert park.base_id == site.installation_id
        assert np.hypot(*(park.center - site.origin)) == pytest.approx(2200, abs=5)
    public = [p for p in world.parks if p.base_id is None]
    assert len(public) == 6  # the original parks host public events (D-005)


def test_county_rd_12_shape(cfg, world) -> None:
    road = world.road("County Rd 12")
    pts = road.points
    seg = np.hypot(*np.diff(pts, axis=0).T)
    assert seg.max() <= ROAD_SPACING_M + 1e-6
    assert seg.min() >= 0.9 * ROAD_SPACING_M
    p1 = next(p for p in cfg.actors.probers if p.id == "P1")
    launches = {
        b: nominal_launch(world.sites[b], "fuel_farm", p1.launch.bearing_deg, p1.launch.distance_m)
        for b in ("ALPHA", "BRAVO", "DELTA")
    }
    for b, pt in launches.items():  # the road passes through each launch point (D-006)
        assert road.line.distance(shapely.Point(pt)) < 1e-6, b
    # straight, west to east, extended 4 km at each end
    order = sorted(launches, key=lambda b: launches[b][0])
    assert order == ["ALPHA", "DELTA", "BRAVO"]
    assert np.hypot(*(pts[0] - launches["ALPHA"])) == pytest.approx(4000, abs=1e-6)
    assert np.hypot(*(pts[-1] - launches["BRAVO"])) == pytest.approx(4000, abs=1e-6)
    expected_len = 8000 + sum(
        np.hypot(*(launches[a] - launches[b])) for a, b in itertools.pairwise(order)
    )
    assert road.line.length == pytest.approx(expected_len, rel=1e-9)
    # CHARLIE is far from the road: P1 keeps its nominal launch there
    charlie = nominal_launch(world.sites["CHARLIE"], "flight_line", 315.0, 2100.0)
    assert road.line.distance(shapely.Point(charlie)) > 500


@pytest.mark.parametrize("base", ["ALPHA", "BRAVO", "DELTA"])
def test_road_within_250_m_of_p1_launch_with_jitter(world, base) -> None:
    road = world.road("County Rd 12")
    nominal = nominal_launch(world.sites[base], "fuel_farm", 315.0, 2100.0)
    rng = np.random.default_rng(0)
    for _ in range(50):
        jittered = nominal + rng.uniform(-150, 150, 2)
        snapped = snap_to_road(jittered, road, nominal)
        assert road.line.distance(shapely.Point(snapped)) < 1e-6
        assert np.hypot(*(snapped - nominal)) <= 250


def test_snap_skips_far_roads(world) -> None:
    road = world.road("County Rd 12")
    far = np.array([60000.0, 60000.0])
    np.testing.assert_array_equal(snap_to_road(far, road, far), far)


def test_push_out_rule(world) -> None:
    site = world.sites["ECHO"]
    mun = site.assets["munitions"].centroid
    inside = geo.destination(mun, 270.0, 700.0)  # C2's nominal launch: inside the fence
    assert site.fence.contains(shapely.Point(inside))
    out = push_out(site.fence, mun, inside)
    assert site.fence.distance(shapely.Point(out)) == pytest.approx(300.0, abs=1e-3)
    assert float(geo.bearing(mun, out)) == pytest.approx(270.0, abs=1e-6)
    near = geo.destination(site.origin, 0.0, 1000.0 + 100.0)  # 100 m outside the north fence
    out = push_out(site.fence, site.origin, near)
    assert site.fence.distance(shapely.Point(out)) == pytest.approx(300.0, abs=1e-3)
    far = geo.destination(site.origin, 0.0, 2000.0)
    np.testing.assert_array_equal(push_out(site.fence, site.origin, far), far)


def test_ray_exit_distance(world) -> None:
    golf = world.sites["GOLF"]  # rotation 0: fence ±1300 east-west, ±1000 north-south
    assert ray_exit_distance(golf.fence, golf.origin, 0.0) == pytest.approx(1000.0)
    assert ray_exit_distance(golf.fence, golf.origin, 90.0) == pytest.approx(1300.0)


def test_bravo_terrain_mask(world) -> None:
    bravo = world.sites["BRAVO"]
    north = geo.wrap360(0.0 + bravo.rotation_deg)  # straight out of the north fence
    edge = ray_exit_distance(bravo.fence, bravo.origin, float(north))
    xy = geo.destination(
        bravo.origin, np.full(6, north), [edge + 40, edge + 60, 2500, 2500, 2500, 2500]
    )
    alt = np.array([100.0, 100.0, 100.0, 250.0, 100.0, 199.0])
    xy[4] = geo.destination(bravo.origin, 90.0, 2500.0)  # east: outside the sector
    np.testing.assert_array_equal(bravo.masked(xy, alt), [False, True, True, False, False, True])
    # the sector wraps through north: just inside 285° and 20° is in, just outside is out
    ring = geo.destination(bravo.origin, np.array([285.5, 19.5, 20.5, 284.5]), np.full(4, 3000.0))
    np.testing.assert_array_equal(bravo.masked(ring, np.full(4, 100.0)), [True, True, False, False])
    golf = world.sites["GOLF"]
    assert not golf.masked(
        geo.destination(golf.origin, 330.0, 3000.0)[None], np.array([50.0])
    ).any()


def test_world_tables_match_ddl(world) -> None:
    tables = world.tables()
    for name, df in tables.items():
        assert list(df.columns) == RAW_COLUMNS[name], name
    assert len(tables["assets"]) == 60
    assert len(tables["sensors"]) == 36
    assert tables["roads"].road_id.is_unique


def test_live_target_is_not_jittered(cfg, world) -> None:
    """D-033 (b): BRAVO's fuel farm (the live P1 target) sits at its template place; every other
    asset keeps its seeded jitter."""
    from kairos_defense.sim.world import unjittered_assets

    assert unjittered_assets(cfg) == {("BRAVO", "fuel_farm")}
    for sid, site in world.sites.items():
        for kind, a in site.assets.items():
            tpl = cfg.world.installation_template.assets[kind].center
            nominal = geo.installation_to_region(tpl, site.origin, site.rotation_deg)
            off = float(np.hypot(*(a.centroid - nominal)))
            if (sid, kind) == ("BRAVO", "fuel_farm"):
                assert off == pytest.approx(0.0, abs=1e-9)
            else:
                assert off > 0.0, (sid, kind)
