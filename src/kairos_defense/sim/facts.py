"""What the paperwork knows about an incident (SPEC §8.8): observed facts plus the true clue values.

Observed: times, mean radar position, median radar altitude, the place it happened near (the
target asset, or the side of the fence for fence targets) and the Remote ID serial received.
True values (for the clue model and ``clue_truth``): the actor's vehicle (probers' config
profile), the road (P1's ``clues.road``, else the region road nearest the launch point), the
departure direction (compass direction from the mean radar position to the true recovery point),
and a per-actor profile of lights, sound and launch site drawn once from
``rng_for(seed, "profile", actor_id)`` (D-040). Hobbyists launched from their park, so the park
is their launch site.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import shapely

from kairos_defense import geo
from kairos_defense.config import Config
from kairos_defense.rng import rng_for
from kairos_defense.sim import lexicon as lx
from kairos_defense.sim.incidents import Incident
from kairos_defense.sim.world import World

ASSET_NAMES = {
    "fuel_farm": "fuel farm",
    "flight_line": "flight line",
    "munitions": "munitions area",
    "hq": "headquarters",
    "housing": "housing area",
}


@dataclass(frozen=True)
class IncidentFacts:
    incident_id: str
    key: str  # stream name: the flight key or swarm event key
    installation_id: str
    installation_name: str
    region_id: str
    utc_offset_hours: int
    actor_id: str  # truth
    actor_type: str  # truth: hobbyist | prober | copycat | swarm
    status: str
    n_drones: int  # tracks seen
    start_ms: int
    end_ms: int
    launch_ms: int  # truth
    xy: tuple[float, float]  # mean radar position, region m
    alt_m: float  # median radar altitude
    near: str  # "fuel farm", "north fence"
    rid_mode: str  # truth: on | off | spoofed
    rid_serial: str | None  # serial received, if any
    vehicle: str | None  # true vehicle, None if the actor has none
    road: str  # true road
    departure: str  # true departure direction
    lights: str
    sound: str
    launch_site: str
    roads: tuple[str, ...]  # the region's road names
    parks: tuple[str, ...]  # every park name (for the clue scanner)


def actor_profile(seed: int, actor_id: str) -> tuple[str, str, str]:
    """The actor's lights, sound and launch-site description (stable per actor)."""
    rng = rng_for(seed, "profile", actor_id)
    pick = [int(rng.integers(len(v))) for v in (lx.LIGHTS, lx.SOUNDS, lx.LAUNCH_SITES)]
    return lx.LIGHTS[pick[0]], lx.SOUNDS[pick[1]], lx.LAUNCH_SITES[pick[2]]


def _vehicles(cfg: Config) -> dict[str, str]:
    return {p.id: p.clues.vehicle for p in cfg.actors.probers if p.clues.vehicle}


def _clue_roads(cfg: Config) -> dict[str, str]:
    return {p.id: p.clues.road for p in cfg.actors.probers if p.clues.road}


def nearest_road(world: World, region_id: str, xy) -> str:
    roads = [r for r in world.roads if r.region_id == region_id]
    p = shapely.Point(xy)
    return min(roads, key=lambda r: (r.line.distance(p), r.name)).name


def incident_facts(cfg: Config, world: World, inc: Incident, seed: int) -> IncidentFacts:
    p = inc.plan
    site = world.sites[p.installation_id]
    xyz = np.concatenate([r.hits.xyz for r in inc.tracks])
    xy = xyz[:, :2].mean(axis=0)
    if p.target_kind in site.assets:
        near = ASSET_NAMES[p.target_kind]
    else:
        near = f"{lx.compass8(float(geo.bearing(site.origin, xy)))} fence"
    first = inc.flights[0]
    recovery = first.path.xyz[-1, :2]
    rid = next((r.rid for r in inc.flights if len(r.rid)), None)
    launch = first.path.xyz[0, :2]
    lights, sound, site_desc = actor_profile(seed, p.actor_id)
    if p.actor_type == "hobbyist":
        park = min(world.parks, key=lambda k: float(np.hypot(*(k.center - launch))))
        site_desc = lx.park_name(park.park_id)
    road = _clue_roads(cfg).get(p.actor_id) or nearest_road(world, p.region_id, launch)
    return IncidentFacts(
        incident_id=inc.incident_id,
        key=inc.key,
        installation_id=p.installation_id,
        installation_name=f"Installation {p.installation_id.title()}",
        region_id=p.region_id,
        utc_offset_hours=site.utc_offset_hours,
        actor_id=p.actor_id,
        actor_type=p.actor_type,
        status=p.status,
        n_drones=len(inc.tracks),
        start_ms=inc.start_ms,
        end_ms=inc.end_ms,
        launch_ms=p.launch_ms,
        xy=(round(float(xy[0]), -1), round(float(xy[1]), -1)),
        alt_m=float(np.median(xyz[:, 2])),
        near=near,
        rid_mode=p.rid,
        rid_serial=rid.serial if rid is not None else None,
        vehicle=_vehicles(cfg).get(p.actor_id),
        road=road,
        departure=lx.compass8(float(geo.bearing(xy, recovery))),
        lights=lights,
        sound=sound,
        launch_site=site_desc,
        roads=tuple(r.name for r in world.roads if r.region_id == p.region_id),
        parks=tuple(lx.park_name(k.park_id) for k in world.parks),
    )
