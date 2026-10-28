"""Flight patterns (SPEC §8.4) as pure geometry over region-frame meters.

Each function returns a ``PatternPath``: a dense polyline whose first point is where the pattern
starts (the pattern point nearest the entry point, §8.3), a nominal horizontal speed per segment
and, where the pattern dictates it, fixed nominal durations (hover, holds) or altitudes (dips).
Time warp is applied later, in ``kinematics``; nothing here depends on it.

Conventions: bearings are true bearings (clockwise from north); ``ccw`` means counter-clockwise as
seen from above on a north-up map, so the bearing from the target to the drone *decreases* (D-024).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import shapely
from shapely.geometry import LineString
from shapely.geometry.polygon import orient

from kairos_defense import geo
from kairos_defense.sim.world import Asset, Site, ray_exit_distance

ORBIT_STEP_DEG = 2.0
FIGURE8_STEP_DEG = 1.0
PERIMETER_STEP_M = 10.0
HOVER_WANDER_KNOT_S = 10  # hover anchor drifts between knots this far apart
HOVER_JITTER_M = 1.0  # §8.3: hover adds N(0, 1 m) position jitter
ENTRY_MARGIN_M = 300.0  # entry point = target + (pattern size + 300 m) along the approach (§8.3)
DIP_HALF_WIDTH_M = 175.0
DIP_FLAT_M = 25.0  # half-length of the level run at dip altitude
WALK_RADIUS_M = 400.0
WALK_HOLD_S = (2.0, 10.0)
FENCE_CROSS_DEPTH_M = 150.0


@dataclass(frozen=True)
class PatternPath:
    xy: np.ndarray  # (n, 2) region meters; xy[0] is the pattern start
    speed: np.ndarray  # (n - 1,) nominal horizontal speed per segment, m/s
    dur: np.ndarray  # (n - 1,) fixed nominal duration per segment in s, NaN = derive from speed
    alt: np.ndarray | None = None  # (n,) altitude per point; None = hold the flight altitude

    def __post_init__(self) -> None:
        n = len(self.xy)
        if self.speed.shape != (n - 1,) or self.dur.shape != (n - 1,):
            raise ValueError("speed and dur need one value per segment")


def _path(xy, speed, dur=None, alt=None) -> PatternPath:
    xy = np.asarray(xy, dtype=np.float64)
    n = len(xy) - 1
    sp = np.broadcast_to(np.asarray(speed, dtype=np.float64), (n,)).copy()
    du = np.full(n, np.nan) if dur is None else np.asarray(dur, dtype=np.float64)
    return PatternPath(xy, sp, du, None if alt is None else np.asarray(alt, dtype=np.float64))


def _axes(axis_bearing_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Unit vectors along and across (90° clockwise of) an axis bearing."""
    return geo.heading_vector(axis_bearing_deg), geo.heading_vector(axis_bearing_deg + 90.0)


# ------------------------------------------------------------------------------------------ size


def pattern_size(pattern: dict, site: Site, target: Asset, approach_deg: float) -> float:
    """Distance (m) from the target centroid to the pattern's outer edge along the approach.

    Orbit: radius. Figure-eight: 2 × lobe radius (its long half-axis, D-024). Lawnmower: half the
    footprint diagonal. Hover: 0. Perimeter: to the buffered fence. Transit with dips: to the fence.
    """
    kind = pattern["type"]
    if kind == "orbit":
        return float(pattern["radius_m"])
    if kind == "figure8":
        return 2.0 * float(pattern["lobe_radius_m"])
    if kind == "lawnmower":
        across = (pattern["legs"] - 1) * pattern["spacing_m"]
        return float(np.hypot(pattern["leg_m"] / 2.0, across / 2.0))
    if kind == "hover":
        return 0.0
    if kind == "perimeter":
        ring = site.fence.buffer(pattern["offset_m"], quad_segs=8)
        return ray_exit_distance(ring, target.centroid, approach_deg)
    if kind == "transit_dips":
        return ray_exit_distance(site.fence, target.centroid, approach_deg)
    raise ValueError(f"no size for pattern {kind!r}")


def entry_point(pattern: dict, site: Site, target: Asset, approach_deg: float) -> np.ndarray:
    """Target centroid + (pattern size + 300 m) along the approach bearing (§8.3); ``(2,)``."""
    size = pattern_size(pattern, site, target, approach_deg)
    return geo.destination(target.centroid, approach_deg, size + ENTRY_MARGIN_M)


# -------------------------------------------------------------------------------------- patterns


def orbit(
    center, radius_m: float, direction: str, laps: int, angular_speed_dps: float, entry_xy
) -> PatternPath:
    """``laps`` circles of ``radius_m`` around ``center``, starting at the circle point nearest
    ``entry_xy``. Speed is ``radius × angular speed`` (rad/s)."""
    if direction not in ("cw", "ccw"):
        raise ValueError(f"orbit direction must be cw or ccw, got {direction!r}")
    b0 = float(geo.bearing(center, entry_xy))
    sign = -1.0 if direction == "ccw" else 1.0
    steps = round(360.0 * laps / ORBIT_STEP_DEG)
    b = b0 + sign * ORBIT_STEP_DEG * np.arange(steps + 1)
    xy = geo.destination(center, b, np.full(len(b), float(radius_m)))
    return _path(xy, radius_m * np.radians(angular_speed_dps))


def lawnmower(
    center, axis_bearing_deg: float, leg_m: float, spacing_m: float, legs: int, speed_ms: float,
    entry_xy,
) -> PatternPath:  # fmt: skip
    """Boustrophedon of ``legs`` parallel legs along the target long axis, centered on it, starting
    at the footprint corner nearest ``entry_xy``."""
    along, across = _axes(axis_bearing_deg)
    offs = (np.arange(legs) - (legs - 1) / 2.0) * spacing_m
    pts = []
    for i, o in enumerate(offs):
        ends = [-leg_m / 2.0, leg_m / 2.0] if i % 2 == 0 else [leg_m / 2.0, -leg_m / 2.0]
        pts += [np.asarray(center) + o * across + e * along for e in ends]
    xy = np.asarray(pts)
    variants = [xy, xy[::-1], _mirror(xy, center, along), _mirror(xy, center, along)[::-1]]
    best = min(variants, key=lambda v: float(np.hypot(*(v[0] - np.asarray(entry_xy)))))
    return _path(best, speed_ms)


def _mirror(xy: np.ndarray, center, along: np.ndarray) -> np.ndarray:
    """Reflect points across the line through ``center`` perpendicular to ``along``."""
    rel = xy - np.asarray(center)
    return xy - 2.0 * np.outer(rel @ along, along)


def figure8(
    center, axis_bearing_deg: float, lobe_radius_m: float, loops: int, speed_ms: float, entry_xy
) -> PatternPath:
    """Lemniscate of Gerono ``u = a cos t, v = (a/2) sin 2t`` with ``a = 2 × lobe radius``, its long
    axis along ``axis_bearing_deg``; starts at the curve point nearest ``entry_xy``."""
    a = 2.0 * lobe_radius_m
    along, across = _axes(axis_bearing_deg)
    grid = np.radians(np.arange(0.0, 360.0, FIGURE8_STEP_DEG))
    curve = _gerono(center, a, along, across, grid)
    t0 = grid[int(np.argmin(np.hypot(*(curve - np.asarray(entry_xy)).T)))]
    t = t0 + np.radians(np.arange(0.0, 360.0 * loops + 1e-9, FIGURE8_STEP_DEG))
    return _path(_gerono(center, a, along, across, t), speed_ms)


def _gerono(center, a: float, along, across, t: np.ndarray) -> np.ndarray:
    u, v = a * np.cos(t), 0.5 * a * np.sin(2.0 * t)
    return np.asarray(center) + u[:, None] * along + v[:, None] * across


def perimeter(fence, offset_m: float, fraction: float, speed_ms: float, entry_xy) -> PatternPath:
    """Follow the fence buffered outward by ``offset_m`` clockwise (D-024) for ``fraction`` of its
    length, from the ring point nearest ``entry_xy``."""
    ring = orient(fence.buffer(offset_m, quad_segs=8), sign=-1.0).exterior  # clockwise
    length = ring.length
    s0 = ring.project(shapely.Point(entry_xy))
    n = max(2, int(np.ceil(fraction * length / PERIMETER_STEP_M)) + 1)
    s = np.mod(s0 + np.linspace(0.0, fraction * length, n), length)
    xy = shapely.get_coordinates(shapely.line_interpolate_point(LineString(ring.coords), s))
    return _path(xy, speed_ms)


def hover(center, dwell_s: float, jitter_m: float, rng: np.random.Generator) -> PatternPath:
    """Hold above ``center`` for ``dwell_s``: the anchor wanders by ``N(0, jitter_m)`` between
    10-s knots, plus ``N(0, 1 m)`` per second; one point per nominal second."""
    n = max(2, round(dwell_s) + 1)
    knots = np.arange(0, n + HOVER_WANDER_KNOT_S, HOVER_WANDER_KNOT_S)
    wander = rng.normal(0.0, jitter_m, (len(knots), 2))
    wander[0] = 0.0  # start exactly over the target
    t = np.arange(n)
    off = np.column_stack([np.interp(t, knots, wander[:, i]) for i in range(2)])
    off[1:] += rng.normal(0.0, HOVER_JITTER_M, (n - 1, 2))
    return _path(np.asarray(center) + off, np.nan, np.ones(n - 1))


def transit_dips(
    site: Site, target: Asset, approach_deg: float, transit_alt_m: float, dip_alt_m: float,
    dips: int, speed_ms: float,
) -> PatternPath:  # fmt: skip
    """Straight pass across the base at ``transit_alt_m`` through the target, from 300 m past the
    fence on the approach side to 300 m past it on the far side (along the pass line), dipping to
    ``dip_alt_m`` over the target and the ``dips - 1`` other assets nearest the pass line. Dips are
    flown slowly enough for the climb limit (durations come from the vertical rate in
    ``kinematics``)."""
    t = target.centroid
    d_in = ray_exit_distance(site.fence, t, approach_deg) + ENTRY_MARGIN_M
    d_out = ray_exit_distance(site.fence, t, approach_deg + 180.0) + ENTRY_MARGIN_M
    start = geo.destination(t, approach_deg, d_in)
    u = geo.heading_vector(approach_deg + 180.0)  # direction of travel
    total = d_in + d_out
    cands = []
    for a in site.assets.values():
        s = float((a.centroid - start) @ u)
        rel = a.centroid - start
        perp = abs(float(u[0] * rel[1] - u[1] * rel[0]))
        if 0.0 < s < total:
            cands.append((0.0 if a.kind == target.kind else perp, s))
    s_dip = sorted(s for _, s in sorted(cands)[:dips])
    edges = np.r_[0.0, s_dip, total]
    s_pts, alts = [0.0], [transit_alt_m]
    for k, sk in enumerate(s_dip):
        room = min(sk - edges[k], edges[k + 2] - sk) / 2.0
        hw = max(min(DIP_HALF_WIDTH_M, room), DIP_FLAT_M + 5.0)
        flat = min(DIP_FLAT_M, hw / 3.0)
        s_pts += [sk - hw, sk - flat, sk + flat, sk + hw]
        alts += [transit_alt_m, dip_alt_m, dip_alt_m, transit_alt_m]
    s_pts.append(total)
    alts.append(transit_alt_m)
    s_arr = np.maximum.accumulate(np.clip(np.asarray(s_pts), 0.0, total))
    xy = start + s_arr[:, None] * u
    return _path(xy, speed_ms, alt=np.asarray(alts))


def random_walk(
    launch_xy, home_xy, speed_ms: float, budget_s: float, cross_xy, rng: np.random.Generator
) -> PatternPath:
    """Hobbyist wander from ``launch_xy`` between goal points within 400 m of it, holding 2-10 s at
    each; ``cross_xy`` (a point just inside the fence) is visited first when given. Goals are added
    while the walk plus the flight back to ``home_xy`` fits in ``budget_s`` nominal seconds."""
    launch = np.asarray(launch_xy, dtype=np.float64)
    home = np.asarray(home_xy, dtype=np.float64)
    pts, speeds, durs = [launch], [], []
    used = 0.0
    queue = [np.asarray(cross_xy, dtype=np.float64)] if cross_xy is not None else []
    for _ in range(200):
        if queue:
            goal = queue.pop(0)
        else:
            r = WALK_RADIUS_M * np.sqrt(rng.random())
            goal = geo.destination(launch, rng.uniform(0.0, 360.0), r)
        hold = rng.uniform(*WALK_HOLD_S)
        leg = float(np.hypot(*(goal - pts[-1]))) / speed_ms
        back = float(np.hypot(*(goal - home))) / speed_ms
        if used + leg + hold + back > budget_s:
            break
        pts += [goal, goal]
        speeds += [speed_ms, np.nan]
        durs += [np.nan, hold]
        used += leg + hold
    if len(pts) == 1:  # not even one goal fits: hover at the launch point
        pts.append(launch.copy())
        speeds.append(np.nan)
        durs.append(max(1.0, budget_s - float(np.hypot(*(launch - home))) / speed_ms))
    return _path(np.asarray(pts), np.asarray(speeds), np.asarray(durs))


def fence_crossing_goal(site: Site, launch_xy) -> np.ndarray:
    """A goal 150 m inside the fence, past the fence point nearest ``launch_xy``; ``(2,)``."""
    p = shapely.Point(launch_xy)
    edge = np.asarray(site.fence.exterior.interpolate(site.fence.exterior.project(p)).coords[0])
    inward = site.origin - edge
    return edge + FENCE_CROSS_DEPTH_M * inward / np.hypot(*inward)
