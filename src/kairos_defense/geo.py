"""Geometry helpers in local ENU meters (``x`` east, ``y`` north).

Bearings are true bearings in the region frame: degrees clockwise from north in [0, 360) (D-007).
Rotations are clockwise (compass sense): rotating a vector by ``r`` adds ``r`` to its bearing.
Point arrays have shape ``(..., 2)`` float64; scalars broadcast. Frames (SPEC §6.2, §9.2):

- installation-local: the template frame, before the installation's ``rotation_deg``;
- region: installation-local rotated clockwise by ``rotation_deg`` then shifted by ``origin_m``;
- target-relative: region frame shifted so the target centroid is at the origin (no rotation).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from shapely import affinity
from shapely.geometry import Polygon

FloatArray = NDArray[np.float64]


def wrap360(deg: ArrayLike) -> FloatArray:
    """Wrap angles to [0, 360). Never returns 360.0 or -0.0."""
    out = np.mod(np.asarray(deg, dtype=np.float64), 360.0)
    out = np.where(out >= 360.0, 0.0, out)  # mod of a tiny negative rounds up to 360.0
    return out + 0.0  # turns -0.0 into 0.0


def wrap180(deg: ArrayLike) -> FloatArray:
    """Wrap angles to [-180, 180). 180 maps to -180."""
    return wrap360(np.asarray(deg, dtype=np.float64) + 180.0) - 180.0


def bearing(from_xy: ArrayLike, to_xy: ArrayLike) -> FloatArray:
    """True bearing in degrees [0, 360) from ``from_xy`` to ``to_xy``; ``(..., 2)`` -> ``(...)``.

    Coincident points give 0.
    """
    d = np.asarray(to_xy, dtype=np.float64) - np.asarray(from_xy, dtype=np.float64)
    return wrap360(np.degrees(np.arctan2(d[..., 0], d[..., 1])))


def heading_vector(bearing_deg: ArrayLike) -> FloatArray:
    """Unit ENU vector(s) pointing along ``bearing_deg``; ``(...)`` -> ``(..., 2)``."""
    b = np.radians(np.asarray(bearing_deg, dtype=np.float64))
    return np.stack([np.sin(b), np.cos(b)], axis=-1)


def destination(origin_xy: ArrayLike, bearing_deg: ArrayLike, distance_m: ArrayLike) -> FloatArray:
    """Point(s) ``distance_m`` from ``origin_xy`` along ``bearing_deg``; ``(..., 2)``."""
    dist = np.asarray(distance_m, dtype=np.float64)[..., None]
    return np.asarray(origin_xy, dtype=np.float64) + dist * heading_vector(bearing_deg)


def rotate(xy: ArrayLike, deg: float, about: ArrayLike = (0.0, 0.0)) -> FloatArray:
    """Rotate points clockwise by ``deg`` about ``about``; ``(..., 2)`` -> ``(..., 2)``."""
    p = np.asarray(xy, dtype=np.float64) - np.asarray(about, dtype=np.float64)
    r = np.radians(deg)
    c, s = np.cos(r), np.sin(r)
    x, y = p[..., 0], p[..., 1]
    out = np.stack([x * c + y * s, -x * s + y * c], axis=-1)
    return out + np.asarray(about, dtype=np.float64)


def rectangle_polygon(center: ArrayLike, size: ArrayLike, rotation_deg: float = 0.0) -> Polygon:
    """Rectangle of ``size = (east-west width, north-south height)`` meters around ``center``,
    turned clockwise by ``rotation_deg`` about its own center."""
    cx, cy = (float(v) for v in np.asarray(center, dtype=np.float64))
    w, h = (float(v) / 2.0 for v in np.asarray(size, dtype=np.float64))
    if w <= 0 or h <= 0:
        raise ValueError(f"rectangle size must be positive, got {list(np.asarray(size))}")
    poly = Polygon([(cx - w, cy - h), (cx + w, cy - h), (cx + w, cy + h), (cx - w, cy + h)])
    # shapely rotates counter-clockwise for positive angles
    return affinity.rotate(poly, -rotation_deg, origin=(cx, cy)) if rotation_deg else poly


def installation_to_region(
    xy_local: ArrayLike, origin_m: ArrayLike, rotation_deg: float
) -> FloatArray:
    """Installation-local meters -> region meters (rotate clockwise, then shift)."""
    return rotate(xy_local, rotation_deg) + np.asarray(origin_m, dtype=np.float64)


def region_to_installation(
    xy_region: ArrayLike, origin_m: ArrayLike, rotation_deg: float
) -> FloatArray:
    """Region meters -> installation-local meters (inverse of ``installation_to_region``)."""
    return rotate(np.asarray(xy_region, dtype=np.float64) - np.asarray(origin_m), -rotation_deg)


def polygon_to_region(poly: Polygon, origin_m: ArrayLike, rotation_deg: float) -> Polygon:
    """Map an installation-local polygon into the region frame."""
    pts = installation_to_region(np.asarray(poly.exterior.coords), origin_m, rotation_deg)
    return Polygon(pts)


def region_to_target(xy_region: ArrayLike, target_centroid: ArrayLike) -> FloatArray:
    """Region meters -> target-relative meters (shift only, SPEC §9.2)."""
    return np.asarray(xy_region, dtype=np.float64) - np.asarray(target_centroid, dtype=np.float64)


def target_to_region(xy_rel: ArrayLike, target_centroid: ArrayLike) -> FloatArray:
    """Target-relative meters -> region meters (e.g. ghost trails into tonight's frame, §13)."""
    return np.asarray(xy_rel, dtype=np.float64) + np.asarray(target_centroid, dtype=np.float64)
