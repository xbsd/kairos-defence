"""Pattern geometry (SPEC §8.4): one known-answer test per pattern."""

from __future__ import annotations

import numpy as np
import pytest
import shapely

from kairos_defense import geo
from kairos_defense.sim import patterns as pat
from kairos_defense.sim.world import ray_exit_distance


def _bearings(center, xy) -> np.ndarray:
    return geo.bearing(np.asarray(center), xy)


@pytest.mark.parametrize(("direction", "sign"), [("ccw", -1), ("cw", 1)])
def test_orbit(direction: str, sign: int) -> None:
    c = np.array([1000.0, -500.0])
    entry = geo.destination(c, 315.0, 480.0)
    p = pat.orbit(c, 180.0, direction, 2, 3.0, entry)
    np.testing.assert_allclose(np.hypot(*(p.xy - c).T), 180.0, atol=1e-9)
    assert float(_bearings(c, p.xy[:1])[0]) == pytest.approx(315.0)  # nearest circle point
    steps = geo.wrap180(np.diff(_bearings(c, p.xy)))
    assert np.all(np.sign(steps) == sign)  # ccw: bearing from the target decreases (D-024)
    assert abs(steps.sum()) == pytest.approx(720.0)
    np.testing.assert_allclose(p.speed, 180.0 * np.radians(3.0))  # 9.4 m/s (D-004)
    assert np.isnan(p.dur).all()


def test_lawnmower() -> None:
    c = np.array([0.0, 0.0])
    entry = geo.destination(c, 200.0, 660.0)
    p = pat.lawnmower(c, 90.0, 600.0, 80.0, 5, 9.0, entry)  # long axis east-west
    assert len(p.xy) == 10
    legs = p.xy.reshape(5, 2, 2)
    np.testing.assert_allclose(np.hypot(*(legs[:, 1] - legs[:, 0]).T), 600.0)
    np.testing.assert_allclose(legs[:, 0, 1], legs[:, 1, 1], atol=1e-9)  # legs run along the axis
    ys = legs[:, 0, 1]
    np.testing.assert_allclose(np.abs(np.diff(ys)), 80.0)
    dirs = np.sign(legs[:, 1, 0] - legs[:, 0, 0])
    assert np.all(dirs[1:] == -dirs[:-1])  # boustrophedon
    corners = [np.array([sx * 300, sy * 160]) for sx in (-1, 1) for sy in (-1, 1)]
    nearest = min(corners, key=lambda q: np.hypot(*(q - entry)))
    np.testing.assert_allclose(p.xy[0], nearest, atol=1e-9)
    assert pat.pattern_size({"type": "lawnmower", "leg_m": 600, "spacing_m": 80, "legs": 5},
                            None, None, 0) == pytest.approx(np.hypot(300, 160))  # fmt: skip


def test_figure8() -> None:
    c = np.array([500.0, 500.0])
    entry = geo.destination(c, 90.0, 540.0)
    p = pat.figure8(c, 90.0, 120.0, 2, 14.0, entry)
    rel = p.xy - c
    assert np.abs(rel[:, 0]).max() == pytest.approx(240.0, abs=0.1)  # a = 2 × lobe radius
    assert np.abs(rel[:, 1]).max() == pytest.approx(120.0, abs=0.1)  # lobe radius
    np.testing.assert_allclose(p.xy[0], c + np.array([240.0, 0.0]), atol=1e-6)  # nearest entry
    np.testing.assert_allclose(p.xy[-1], p.xy[0], atol=1e-6)  # whole loops
    near_center = np.hypot(*rel.T) < 5.0
    assert near_center.sum() >= 4  # crosses the center twice per loop


def test_perimeter_is_clockwise_at_offset() -> None:
    fence = shapely.box(-1300, -1000, 1300, 1000)
    entry = np.array([0.0, 1500.0])
    p = pat.perimeter(fence, 200.0, 0.5, 15.0, entry)
    d = np.asarray(shapely.distance(shapely.points(p.xy), fence))
    np.testing.assert_allclose(d, 200.0, atol=1.0)
    np.testing.assert_allclose(p.xy[0], [0.0, 1200.0], atol=1e-6)
    steps = geo.wrap180(np.diff(_bearings((0, 0), p.xy)))
    assert (steps > 0).all()  # clockwise seen from above (D-024)
    ring = fence.buffer(200.0, quad_segs=8).exterior.length
    length = np.hypot(*np.diff(p.xy, axis=0).T).sum()
    assert length == pytest.approx(0.5 * ring, rel=0.01)


def test_hover() -> None:
    rng = np.random.default_rng(1)
    c = np.array([10.0, 20.0])
    p = pat.hover(c, 300.0, 6.0, rng)
    assert len(p.xy) == 301
    np.testing.assert_allclose(p.dur, 1.0)
    np.testing.assert_allclose(p.xy[0], c)
    r = np.hypot(*(p.xy - c).T)
    assert r.max() < 6 * 6.0
    assert 2.0 < r.mean() < 15.0


def test_transit_dips(world) -> None:
    site = world.sites["GOLF"]
    target = site.assets["housing"]
    p = pat.transit_dips(site, target, 250.0, 300.0, 80.0, 3, 18.0)
    # starts and ends 300 m past the fence along the pass line (entry rule, §8.3)
    d_in = ray_exit_distance(site.fence, target.centroid, 250.0)
    d_out = ray_exit_distance(site.fence, target.centroid, 70.0)
    assert np.hypot(*(p.xy[0] - target.centroid)) == pytest.approx(d_in + 300.0)
    assert np.hypot(*(p.xy[-1] - target.centroid)) == pytest.approx(d_out + 300.0)
    assert float(geo.bearing(target.centroid, p.xy[0])) == pytest.approx(250.0)
    line = shapely.LineString(p.xy)
    assert line.distance(shapely.Point(target.centroid)) < 1e-6  # passes over the target
    low = p.alt == 80.0
    assert ((low[1:] & ~low[:-1]).sum()) == 3  # three dips
    assert p.alt[0] == p.alt[-1] == 300.0


def test_random_walk_fits_budget_and_radius() -> None:
    rng = np.random.default_rng(3)
    launch = np.array([0.0, 0.0])
    home = np.array([100.0, 50.0])
    p = pat.random_walk(launch, home, 8.0, 400.0, None, rng)
    assert np.hypot(*(p.xy - launch).T).max() <= 400.0 + 1e-9
    moves = np.isnan(p.dur)
    seg = np.hypot(*np.diff(p.xy, axis=0).T)
    t = (seg[moves] / 8.0).sum() + p.dur[~moves].sum()
    back = np.hypot(*(p.xy[-1] - home)) / 8.0
    assert t + back <= 400.0
    assert p.dur[~moves].min() >= 2.0
    assert p.dur[~moves].max() <= 10.0


def test_fence_crossing_goal(world) -> None:
    site = world.sites["ALPHA"]
    park = world.park(site.park_id)
    goal = pat.fence_crossing_goal(site, park.center)
    assert site.fence.contains(shapely.Point(goal))
    assert site.fence.exterior.distance(shapely.Point(goal)) == pytest.approx(150.0, abs=1.0)


def test_entry_point_distances(world) -> None:
    site = world.sites["GOLF"]
    ff = site.assets["fuel_farm"]
    orbit = {"type": "orbit", "radius_m": 180.0}
    e = pat.entry_point(orbit, site, ff, 315.0)
    assert np.hypot(*(e - ff.centroid)) == pytest.approx(480.0)
    fig8 = {"type": "figure8", "lobe_radius_m": 120.0}
    assert pat.pattern_size(fig8, site, ff, 0.0) == 240.0  # D-024
    fence = site.target("fence")
    per = {"type": "perimeter", "offset_m": 200.0}
    e = pat.entry_point(per, site, fence, 0.0)
    assert np.hypot(*(e - fence.centroid)) == pytest.approx(1000 + 200 + 300)
