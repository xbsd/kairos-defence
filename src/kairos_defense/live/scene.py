"""What the 3D theater draws for one installation (SPEC §16.4 ``…/scene``, §17.3, D-109).

Region-frame meters, as in the database; the web app subtracts the installation origin. Roads are
clipped and parks kept within ``radius_m`` of the origin (the grid fades there). The radar shadow
is the terrain-mask sector of the world configuration (§8.6: seen from the origin, beyond the
fence by ``beyond_fence_m``, below ``below_alt_m``) out to the radar's range: configuration, not
truth.
"""

from __future__ import annotations

import json

import numpy as np
from shapely import wkt
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from kairos_defense.config.world import WorldConfig
from kairos_defense.ports import TrackStore

SCENE_RADIUS_M = 6000.0


def _ring(poly: Polygon) -> list[tuple[float, float]]:
    return [(round(x, 2), round(y, 2)) for x, y in poly.exterior.coords]


def _lines(g: BaseGeometry) -> list[list[tuple[float, float]]]:
    if g.is_empty:
        return []
    parts = g.geoms if isinstance(g, MultiLineString) else [g] if isinstance(g, LineString) else (
        [p for p in getattr(g, "geoms", []) if isinstance(p, LineString)])  # fmt: skip
    return [[(round(x, 2), round(y, 2)) for x, y in p.coords] for p in parts if not p.is_empty]


def _polygons(g: BaseGeometry) -> list[list[tuple[float, float]]]:
    if g.is_empty:
        return []
    parts = getattr(g, "geoms", [g])
    return [_ring(p) for p in parts if isinstance(p, Polygon) and not p.is_empty]


def sector(origin: tuple[float, float], lo: float, hi: float, radius: float,
           step_deg: float = 2.0) -> Polygon:  # fmt: skip
    """Clockwise sector from bearing ``lo`` to ``hi`` (degrees from north, may wrap 0)."""
    span = (hi - lo) % 360.0
    brg = np.radians(lo + np.linspace(0.0, span, max(2, int(span / step_deg) + 1)))
    ox, oy = origin
    arc = [(ox + radius * np.sin(b), oy + radius * np.cos(b)) for b in brg]
    return Polygon([origin, *arc, origin])


def _mask(world: WorldConfig, installation_id: str):
    for r in world.regions:
        for i in r.installations:
            if i.id == installation_id:
                return i.terrain_mask
    return None


def installation_scene(store: TrackStore, world: WorldConfig, installation_id: str,
                       radius_m: float = SCENE_RADIUS_M) -> dict:  # fmt: skip
    """The ``Scene`` body (``api.schemas.Scene``); ``KeyError`` for an unknown installation."""
    from kairos_defense.sim.lexicon import park_name

    inst = store.sql("SELECT i.*, g.utc_offset_hours FROM installations i JOIN regions g "
                     "USING (region_id) WHERE installation_id = $i",
                     {"i": installation_id})  # fmt: skip
    if inst.empty:
        raise KeyError(f"no installation {installation_id!r}")
    row = inst.iloc[0]
    origin = (float(row["origin_x_m"]), float(row["origin_y_m"]))
    disc = Point(origin).buffer(radius_m, quad_segs=64)
    fence = wkt.loads(row["fence_wkt"])
    q = {"i": installation_id, "r": str(row["region_id"])}
    adf = store.sql("SELECT * FROM assets WHERE installation_id = $i ORDER BY asset_id",
                    {"i": installation_id})  # fmt: skip
    assets = [{"asset_id": a.asset_id, "kind": a.kind, "polygon": _ring(wkt.loads(a.polygon_wkt)),
               "centroid_x_m": float(a.centroid_x_m), "centroid_y_m": float(a.centroid_y_m)}
              for a in adf.itertuples()]  # fmt: skip
    roads = []
    for rd in store.sql("SELECT name, line_wkt FROM roads WHERE region_id = $r ORDER BY name",
                        {"r": q["r"]}).itertuples():  # fmt: skip
        lines = _lines(wkt.loads(rd.line_wkt).intersection(disc))
        if lines:
            roads.append({"name": rd.name, "lines": lines})
    parks = [{"park_id": p.park_id, "name": park_name(p.park_id),
              "center_x_m": float(p.center_x_m), "center_y_m": float(p.center_y_m),
              "radius_m": float(p.radius_m)}
             for p in store.sql("SELECT * FROM parks WHERE region_id = $r ORDER BY park_id",
                                {"r": q["r"]}).itertuples()
             if Point(p.center_x_m, p.center_y_m).distance(Point(origin)) <= radius_m]  # fmt: skip
    sensors = []
    radar_range = None
    for s in store.sql("SELECT * FROM sensors WHERE installation_id = $i ORDER BY sensor_id",
                       {"i": installation_id}).itertuples():  # fmt: skip
        params = json.loads(s.params) if isinstance(s.params, str) else (s.params or {})
        sensors.append({"sensor_id": s.sensor_id, "kind": s.kind, "x_m": float(s.x_m),
                        "y_m": float(s.y_m), "range_m": float(s.range_m),
                        "rate_hz": params.get("rate_hz")})  # fmt: skip
        if s.kind == "radar":
            radar_range = float(s.range_m)
    shadow = None
    m = _mask(world, installation_id)
    if m is not None:
        lo, hi = m.bearing_deg
        wedge = sector(origin, lo, hi, radar_range or radius_m).difference(
            fence.buffer(m.beyond_fence_m, quad_segs=32))  # fmt: skip
        shadow = {"label": "Radar shadow", "bearing_deg": (float(lo), float(hi)),
                  "beyond_fence_m": float(m.beyond_fence_m), "below_alt_m": float(m.below_alt_m),
                  "polygons": _polygons(wedge)}  # fmt: skip
    return {"installation_id": installation_id, "name": str(row["name"]),
            "region_id": q["r"], "utc_offset_hours": int(row["utc_offset_hours"]),
            "origin_x_m": origin[0], "origin_y_m": origin[1],
            "rotation_deg": float(row["rotation_deg"]), "radius_m": float(radius_m),
            "fence": _ring(fence), "assets": assets, "roads": roads, "parks": parks,
            "sensors": sensors, "radar_shadow": shadow}  # fmt: skip
