"""World build (SPEC §8.1): installations, assets, sensors, parks and roads in region frames.

All coordinates are region-frame ENU meters; bearings are true bearings, clockwise from north
(D-007). The installation template is rotated clockwise by ``rotation_deg``, each asset center is
jittered by ``N(0, jitter_m)`` from its own seeded stream, then everything is shifted by
``origin_m``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Polygon

from kairos_defense import geo
from kairos_defense.config import Config
from kairos_defense.config.world import Region, TerrainMask
from kairos_defense.rng import rng_for

ROAD_SPACING_M = 50.0  # County Rd 12 is densified to this spacing (D-006)
SNAP_WITHIN_M = 500.0  # P1 snaps its launch to the road only this close (D-006)
PUSH_OUT_M = 300.0  # launch points end up at least this far outside the fence (D-005)
BASE_PARK_MAX_M = 3000.0  # an installation's launch park lies within this distance (D-005)


@dataclass(frozen=True)
class Asset:
    """A target: an asset rectangle, or the fence as a pseudo-asset (``kind == "fence"``)."""

    asset_id: str
    installation_id: str
    kind: str
    polygon: Polygon
    centroid: np.ndarray  # (2,) region meters
    axis_bearing_deg: float  # bearing of the long axis, in [0, 360)


@dataclass(frozen=True)
class Sensor:
    sensor_id: str
    installation_id: str
    kind: str  # radar | rf | rid
    xy: np.ndarray  # (2,) region meters
    range_m: float
    params: dict


@dataclass(frozen=True)
class Site:
    """One installation in its region frame."""

    installation_id: str
    region_id: str
    utc_offset_hours: int
    origin: np.ndarray  # (2,)
    rotation_deg: float
    fence: Polygon
    assets: dict[str, Asset]
    sensors: dict[str, Sensor]  # by kind (one per kind in the template)
    terrain_mask: TerrainMask | None
    park_id: str

    def target(self, kind: str) -> Asset:
        """The asset of ``kind``, or the fence pseudo-asset for ``"fence"``."""
        if kind != "fence":
            return self.assets[kind]
        c = np.asarray(self.fence.centroid.coords[0], dtype=np.float64)
        return Asset(
            f"{self.installation_id}-fence", self.installation_id, "fence", self.fence, c,
            float(geo.wrap360(90.0 + self.rotation_deg)),
        )  # fmt: skip

    def fence_distance(self, xy: np.ndarray) -> np.ndarray:
        """Distance (m) from points ``(n, 2)`` to the fence polygon; 0 inside."""
        return np.asarray(shapely.distance(shapely.points(np.asarray(xy)), self.fence))

    def masked(self, xy: np.ndarray, alt_m: np.ndarray) -> np.ndarray:
        """Terrain mask (§8.6, D-003): True where the site's sensors cannot see; ``(n,)`` bool."""
        xy = np.asarray(xy, dtype=np.float64)
        alt_m = np.asarray(alt_m, dtype=np.float64)
        if self.terrain_mask is None or len(xy) == 0:
            return np.zeros(len(xy), dtype=bool)
        m = self.terrain_mask
        lo, hi = m.bearing_deg
        in_sector = geo.wrap360(geo.bearing(self.origin, xy) - lo) <= geo.wrap360(hi - lo)
        low = alt_m < m.below_alt_m
        out = np.zeros(len(xy), dtype=bool)
        idx = np.flatnonzero(in_sector & low)
        if len(idx):
            out[idx] = self.fence_distance(xy[idx]) > m.beyond_fence_m
        return out


@dataclass(frozen=True)
class Road:
    road_id: str
    region_id: str
    name: str
    line: LineString

    @property
    def points(self) -> np.ndarray:
        return np.asarray(self.line.coords, dtype=np.float64)


@dataclass(frozen=True)
class Park:
    park_id: str
    region_id: str
    center: np.ndarray  # (2,)
    radius_m: float
    base_id: str | None  # the installation whose launch park this is; None for public-event parks


@dataclass(frozen=True)
class World:
    regions: dict[str, int]  # region_id -> utc_offset_hours
    sites: dict[str, Site]
    roads: list[Road]
    parks: list[Park]

    def road(self, name: str) -> Road:
        return next(r for r in self.roads if r.name == name)

    def park(self, park_id: str) -> Park:
        return next(p for p in self.parks if p.park_id == park_id)

    def public_parks(self, region_id: str) -> list[Park]:
        return [p for p in self.parks if p.region_id == region_id and p.base_id is None]

    def tables(self) -> dict[str, pd.DataFrame]:
        """The §7.1 world tables: regions, installations, assets, roads, parks, sensors."""
        return world_tables(self)


# ----------------------------------------------------------------------------------------- build


def build_world(cfg: Config, seed: int) -> World:
    """Build every installation, sensor, park and road from ``cfg.world`` (§8.1)."""
    w = cfg.world
    sites: dict[str, Site] = {}
    parks: list[Park] = []
    roads: list[Road] = []
    for region in w.regions:
        base_parks = _assign_base_parks(region)
        for inst in region.installations:
            sites[inst.id] = _build_site(cfg, seed, region, inst.id, base_parks[inst.id])
        owner = {pid: b for b, pid in base_parks.items()}
        for p in region.parks:
            c = np.asarray(p.center_m, dtype=np.float64)
            parks.append(Park(p.id, region.id, c, float(p.radius_m), owner.get(p.id)))
        for k, road in enumerate(region.roads, start=1):
            if road.build == "through_launch_points":
                pts = _county_road_points(cfg, region, sites, road.actor or "", road.extend_m or 0)
                line = shapely.segmentize(LineString(pts), ROAD_SPACING_M)
            else:
                line = LineString(np.asarray(road.points_m, dtype=np.float64))
            roads.append(Road(f"{region.id}-ROAD-{k}", region.id, road.name, line))
    return World({r.id: r.utc_offset_hours for r in w.regions}, sites, roads, parks)


def _assign_base_parks(region: Region) -> dict[str, str]:
    """Each installation's launch park: the nearest park within 3 km of its origin (D-005)."""
    out = {}
    for inst in region.installations:
        o = np.asarray(inst.origin_m)
        d = {p.id: float(np.hypot(*(np.asarray(p.center_m) - o))) for p in region.parks}
        pid = min(d, key=lambda k: (d[k], k))
        if d[pid] > BASE_PARK_MAX_M:
            raise ValueError(f"{inst.id}: no launch park within {BASE_PARK_MAX_M:.0f} m (D-005)")
        out[inst.id] = pid
    return out


def _build_site(cfg: Config, seed: int, region: Region, inst_id: str, park_id: str) -> Site:
    w = cfg.world
    inst = w.installation(inst_id)
    origin = np.asarray(inst.origin_m, dtype=np.float64)
    rot = float(inst.rotation_deg)
    tpl = w.installation_template
    fence = Polygon(geo.installation_to_region(np.asarray(tpl.fence), origin, rot))
    assets = {}
    for kind, a in tpl.assets.items():
        jitter = rng_for(seed, "world", inst_id, "asset", kind).normal(0.0, tpl.jitter_m, 2)
        center = geo.rotate(a.center, rot) + jitter + origin
        axis = 90.0 + rot if a.size[0] >= a.size[1] else rot
        assets[kind] = Asset(
            f"{inst_id}-{kind}", inst_id, kind, geo.rectangle_polygon(center, a.size, rot),
            center, float(geo.wrap360(axis)),
        )  # fmt: skip
    sensors = {}
    for s in w.sensors_template:
        params = s.model_dump(exclude={"kind", "at", "range_m"})
        xy = geo.installation_to_region(s.at, origin, rot)
        sid = f"{inst_id}-{s.kind.upper()}-1"
        sensors[s.kind] = Sensor(sid, inst_id, s.kind, xy, float(s.range_m), params)
    return Site(
        inst_id, region.id, region.utc_offset_hours, origin, rot, fence, assets, sensors,
        inst.terrain_mask, park_id,
    )  # fmt: skip


def _road_bases(cfg: Config, region: Region, actor_id: str) -> list[str]:
    """Bases the road joins: where the actor's planted flights fly its own target (D-006).

    For P1 that is ALPHA, BRAVO and DELTA (CHARLIE's flight has ``target_override``). An actor with
    no planted flights uses all of its bases in the region.
    """
    in_region = {i.id for i in region.installations}
    planted = set()
    if actor_id == "P1":
        planted = {f.base for f in cfg.scenario.p1_flights if f.target_override is None}
    prober = next(p for p in cfg.actors.probers if p.id == actor_id)
    bases = [b for b in prober.bases if b in in_region and (not planted or b in planted)]
    if len(bases) < 2:
        raise ValueError(f"road for {actor_id}: needs at least two bases in {region.id}")
    return bases


def nominal_launch(site: Site, target_kind: str, bearing_deg: float, distance_m: float):
    """Target centroid + ``distance_m`` along ``bearing_deg``; ``(2,)`` region meters."""
    return geo.destination(site.target(target_kind).centroid, bearing_deg, distance_m)


def _county_road_points(
    cfg: Config, region: Region, sites: dict[str, Site], actor_id: str, extend_m: float
) -> np.ndarray:
    """Straight segments through the actor's nominal launch points, west to east, extended at
    both ends (no corner-cutting, D-006); ``(n, 2)``."""
    prober = next(p for p in cfg.actors.probers if p.id == actor_id)
    pts = np.array(
        [
            nominal_launch(
                sites[b], prober.target, prober.launch.bearing_deg, prober.launch.distance_m
            )
            for b in _road_bases(cfg, region, actor_id)
        ]
    )
    pts = pts[np.argsort(pts[:, 0], kind="stable")]
    head = pts[0] - extend_m * _unit(pts[1] - pts[0])
    tail = pts[-1] + extend_m * _unit(pts[-1] - pts[-2])
    return np.vstack([head, pts, tail])


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.hypot(*v)


# ------------------------------------------------------------------------------ launch geometry


def snap_to_road(point: np.ndarray, road: Road, nominal: np.ndarray) -> np.ndarray:
    """Project ``point`` onto ``road`` if the road passes within 500 m of ``nominal`` (D-006)."""
    if road.line.distance(shapely.Point(nominal)) > SNAP_WITHIN_M:
        return np.asarray(point, dtype=np.float64)
    s = road.line.project(shapely.Point(point))
    return np.asarray(road.line.interpolate(s).coords[0], dtype=np.float64)


def push_out(
    fence: Polygon, target_xy: np.ndarray, point: np.ndarray, min_out_m: float = PUSH_OUT_M
):
    """Move ``point`` outward along the ray from ``target_xy`` until it is at least ``min_out_m``
    outside the fence (D-005); points already that far out are returned unchanged. ``(2,)``."""
    point = np.asarray(point, dtype=np.float64)
    if (
        not fence.contains(shapely.Point(point))
        and fence.distance(shapely.Point(point)) >= min_out_m
    ):
        return point
    target_xy = np.asarray(target_xy, dtype=np.float64)
    b = float(geo.bearing(target_xy, point))
    d0 = float(np.hypot(*(point - target_xy)))
    reach = d0 + 2.0 * min_out_m + float(np.sqrt(fence.area)) * 4.0
    ts = np.arange(d0, reach, 5.0)
    dist = np.asarray(shapely.distance(shapely.points(geo.destination(target_xy, b, ts)), fence))
    ok = np.flatnonzero(dist >= min_out_m)
    if not len(ok):
        raise ValueError("push_out: could not get outside the fence")
    hi = float(ts[ok[0]])
    lo = float(ts[ok[0] - 1]) if ok[0] > 0 else d0
    for _ in range(40):  # bisect to sub-millimeter
        mid = 0.5 * (lo + hi)
        if fence.distance(shapely.Point(geo.destination(target_xy, b, mid))) >= min_out_m:
            hi = mid
        else:
            lo = mid
    return geo.destination(target_xy, b, hi)


def ray_exit_distance(poly: Polygon, origin: np.ndarray, bearing_deg: float) -> float:
    """Distance from ``origin`` (inside ``poly``) along ``bearing_deg`` to the polygon boundary."""
    far = geo.destination(origin, bearing_deg, 1e5)
    hit = LineString([origin, far]).intersection(poly.exterior)
    pts = shapely.get_coordinates(hit)
    if not len(pts):
        return 0.0
    return float(np.min(np.hypot(*(pts - np.asarray(origin)).T)))


# ----------------------------------------------------------------------------------------- tables


def _wkt(geom) -> str:
    return shapely.to_wkt(geom, rounding_precision=3)


def world_tables(world: World) -> dict[str, pd.DataFrame]:
    sites = list(world.sites.values())
    regions = pd.DataFrame(
        {"region_id": list(world.regions), "utc_offset_hours": list(world.regions.values())}
    ).astype({"utc_offset_hours": "int32"})
    installations = pd.DataFrame(
        {
            "installation_id": [s.installation_id for s in sites],
            "name": [f"Installation {s.installation_id.title()}" for s in sites],
            "region_id": [s.region_id for s in sites],
            "origin_x_m": [float(s.origin[0]) for s in sites],
            "origin_y_m": [float(s.origin[1]) for s in sites],
            "rotation_deg": [s.rotation_deg for s in sites],
            "fence_wkt": [_wkt(s.fence) for s in sites],
        }
    )
    assets = [a for s in sites for a in s.assets.values()]
    assets_df = pd.DataFrame(
        {
            "asset_id": [a.asset_id for a in assets],
            "installation_id": [a.installation_id for a in assets],
            "kind": [a.kind for a in assets],
            "polygon_wkt": [_wkt(a.polygon) for a in assets],
            "centroid_x_m": [float(a.centroid[0]) for a in assets],
            "centroid_y_m": [float(a.centroid[1]) for a in assets],
        }
    )
    roads = pd.DataFrame(
        {
            "road_id": [r.road_id for r in world.roads],
            "region_id": [r.region_id for r in world.roads],
            "name": [r.name for r in world.roads],
            "line_wkt": [_wkt(r.line) for r in world.roads],
        }
    )
    parks = pd.DataFrame(
        {
            "park_id": [p.park_id for p in world.parks],
            "region_id": [p.region_id for p in world.parks],
            "center_x_m": [float(p.center[0]) for p in world.parks],
            "center_y_m": [float(p.center[1]) for p in world.parks],
            "radius_m": [p.radius_m for p in world.parks],
        }
    )
    sensors = [s for site in sites for s in site.sensors.values()]
    sensors_df = pd.DataFrame(
        {
            "sensor_id": [s.sensor_id for s in sensors],
            "installation_id": [s.installation_id for s in sensors],
            "kind": [s.kind for s in sensors],
            "x_m": [float(s.xy[0]) for s in sensors],
            "y_m": [float(s.xy[1]) for s in sensors],
            "range_m": [s.range_m for s in sensors],
            "params": [json.dumps(s.params, sort_keys=True) for s in sensors],
        }
    )
    return {
        "regions": regions,
        "installations": installations,
        "assets": assets_df,
        "roads": roads,
        "parks": parks,
        "sensors": sensors_df,
    }
