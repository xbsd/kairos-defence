from __future__ import annotations

import math

import numpy as np
import pytest

from kairos_defense import geo


@pytest.mark.parametrize(
    ("to", "expected"),
    [((0, 10), 0.0), ((10, 0), 90.0), ((0, -10), 180.0), ((-10, 0), 270.0), ((-1, 1), 315.0)],
)
def test_bearing_cardinals(to: tuple[float, float], expected: float) -> None:
    assert float(geo.bearing((0, 0), to)) == pytest.approx(expected)


def test_bearing_vectorized_and_coincident() -> None:
    frm = np.array([[0.0, 0.0], [5.0, 5.0], [1.0, 1.0]])
    to = np.array([[0.0, 1.0], [6.0, 4.0], [1.0, 1.0]])
    np.testing.assert_allclose(geo.bearing(frm, to), [0.0, 135.0, 0.0])


def test_bearing_just_west_of_north_stays_below_360() -> None:
    b = float(geo.bearing((0, 0), (-1e-12, 1.0)))
    assert 0.0 <= b < 360.0


@pytest.mark.parametrize(
    ("deg", "w360", "w180"),
    [
        (0.0, 0.0, 0.0),
        (360.0, 0.0, 0.0),
        (-0.0, 0.0, 0.0),
        (180.0, 180.0, -180.0),
        (-180.0, 180.0, -180.0),
        (190.0, 190.0, -170.0),
        (-10.0, 350.0, -10.0),
        (725.0, 5.0, 5.0),
        (-725.0, 355.0, -5.0),
        (359.999, 359.999, -0.001),
    ],
)
def test_wrap(deg: float, w360: float, w180: float) -> None:
    assert float(geo.wrap360(deg)) == pytest.approx(w360)
    assert float(geo.wrap180(deg)) == pytest.approx(w180)


def test_wrap360_never_returns_360_or_negative_zero() -> None:
    out = geo.wrap360(np.array([-1e-14, -0.0, 360.0, 720.0]))
    assert np.all(out < 360.0)
    assert not np.any(np.signbit(out))


def test_destination_and_heading() -> None:
    np.testing.assert_allclose(geo.destination((100, 100), 90.0, 50.0), [150, 100], atol=1e-9)
    p = geo.destination((0, 0), 315.0, 2100.0)
    assert float(geo.bearing((0, 0), p)) == pytest.approx(315.0)
    assert float(np.hypot(*p)) == pytest.approx(2100.0)
    np.testing.assert_allclose(geo.heading_vector([0, 90]), [[0, 1], [1, 0]], atol=1e-12)


def test_rotate_is_clockwise() -> None:
    np.testing.assert_allclose(geo.rotate((0, 1), 90.0), [1, 0], atol=1e-12)  # north -> east
    np.testing.assert_allclose(geo.rotate((1, 0), 90.0), [0, -1], atol=1e-12)  # east -> south
    np.testing.assert_allclose(geo.rotate((2, 1), 180.0, about=(1, 1)), [0, 1], atol=1e-12)


def test_rotate_adds_to_bearing() -> None:
    p = geo.destination((0, 0), 30.0, 10.0)
    assert float(geo.bearing((0, 0), geo.rotate(p, 12.0))) == pytest.approx(42.0)


def test_rectangle_polygon() -> None:
    r = geo.rectangle_polygon((600, 300), (120, 80))
    assert r.area == pytest.approx(9600)
    assert r.bounds == pytest.approx((540, 260, 660, 340))
    turned = geo.rectangle_polygon((0, 0), (100, 10), rotation_deg=90.0)
    minx, miny, maxx, maxy = turned.bounds  # long side now runs north-south
    assert (maxx - minx, maxy - miny) == pytest.approx((10, 100))
    with pytest.raises(ValueError):
        geo.rectangle_polygon((0, 0), (0, 10))


def test_rectangle_rotation_matches_point_rotation() -> None:
    turned = geo.rectangle_polygon((0, 0), (100, 10), rotation_deg=30.0)
    corner = geo.rotate((50, 5), 30.0)
    assert min(math.dist(corner, c) for c in turned.exterior.coords) == pytest.approx(0, abs=1e-9)


def test_installation_region_round_trip() -> None:
    origin, rot = (22000.0, -6000.0), 12.0  # BRAVO
    local = np.array([[600.0, 300.0], [-1300.0, 1000.0], [0.0, 0.0]])
    region = geo.installation_to_region(local, origin, rot)
    np.testing.assert_allclose(region[2], origin)
    np.testing.assert_allclose(geo.region_to_installation(region, origin, rot), local, atol=1e-9)
    # a point due north of the origin locally lies at bearing 12 in the region frame
    north = geo.installation_to_region((0, 1000), origin, rot)
    assert float(geo.bearing(origin, north)) == pytest.approx(12.0)


def test_polygon_to_region() -> None:
    poly = geo.rectangle_polygon((0, 0), (2600, 2000))
    out = geo.polygon_to_region(poly, (1000, 0), 90.0)
    assert out.area == pytest.approx(poly.area)
    assert out.centroid.coords[0] == pytest.approx((1000, 0))
    minx, miny, maxx, maxy = out.bounds
    assert (maxx - minx, maxy - miny) == pytest.approx((2000, 2600))


def test_target_frame_is_shift_only() -> None:
    c = (9500.0, -23000.0)
    pts = np.array([[9680.0, -23000.0], [9500.0, -22820.0]])
    rel = geo.region_to_target(pts, c)
    np.testing.assert_allclose(rel, [[180, 0], [0, 180]])
    np.testing.assert_allclose(geo.target_to_region(rel, c), pts)
