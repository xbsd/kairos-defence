"""Flights -> sensor detections -> incidents (SPEC §7.1, §8.6, §8.11, D-003, D-028).

``sense`` runs a flight's installation sensors (radar, RF, Remote ID), each from its own stream.
``group_incidents`` turns flights into incidents: a single flight is one incident; the drones of a
swarm event share one. An incident needs at least one radar point (tracks are radar tracks); its
start and end are the first and last detection of any of its drones by *any* sensor (D-028). A
flight heard only by RF or Remote ID makes no incident, but its detections are still logged
(D-038). Generated ids are ``<BASE>-<YYMMDD>-<HHMM>`` of the first detection, local time, with
``-2``, ``-3`` … on a clash; planted incidents keep theirs. Track ids are ``<incident>-T<n>``,
numbered in drone order over the drones the radar saw.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np

from kairos_defense.rng import rng_for
from kairos_defense.sim.calendar import utc_ms_to_local
from kairos_defense.sim.kinematics import FlightPath
from kairos_defense.sim.plan import FlightPlan
from kairos_defense.sim.sensors import (
    RadarHits,
    RfHits,
    RidHits,
    radar_track,
    rf_track,
    rid_track,
    stable_serial,
)
from kairos_defense.sim.world import World


@dataclass(frozen=True)
class FlightResult:
    """One flown drone: its plan, true 1 Hz path and what each sensor detected."""

    plan: FlightPlan
    path: FlightPath  # truth, 1 Hz
    hits: RadarHits
    rf: RfHits
    rid: RidHits

    @property
    def detected(self) -> bool:
        """Seen by the radar (a track exists)."""
        return len(self.hits) > 0

    @property
    def group(self) -> str:
        """The incident group: the swarm event for a swarm drone, else the flight itself."""
        return self.plan.extra.get("swarm", self.plan.key)

    def detection_ms(self) -> np.ndarray:
        """UTC epoch ms of every detection by any sensor, sorted; ``(m,)`` int64."""
        t = np.concatenate([self.hits.t_s, self.rf.t_s, self.rid.t_s])
        return np.sort(self.plan.launch_ms + np.round(t * 1000.0).astype(np.int64))


def sense(plan: FlightPlan, path: FlightPath, world: World, seed: int) -> FlightResult:
    """Radar, RF and Remote ID for one drone; streams are named by the flight key."""
    site = world.sites[plan.installation_id]
    hits = radar_track(path, site, rng_for(seed, "flight", plan.key, "radar"), plan.outage_s)
    rf = rf_track(path, site, plan.rf_family, rng_for(seed, "flight", plan.key, "rf"))
    serial = stable_serial(seed, plan.actor_id, int(plan.extra.get("drone", 0)))
    rid = rid_track(path, site, plan.rid, serial, plan.launch_xy,
                    rng_for(seed, "flight", plan.key, "rid"))  # fmt: skip
    return FlightResult(plan, path, hits, rf, rid)


@dataclass(frozen=True)
class Incident:
    """One incident: every drone flown in it, and the radar-tracked ones in track order."""

    incident_id: str
    key: str  # flight key, or the swarm event key
    flights: tuple[FlightResult, ...]
    tracks: tuple[FlightResult, ...]
    start_ms: int
    end_ms: int

    @property
    def plan(self) -> FlightPlan:
        """The first drone's plan: base, actor, status and times are shared by every drone."""
        return self.flights[0].plan

    @property
    def is_swarm(self) -> bool:
        return self.plan.actor_type == "swarm"

    @property
    def status(self) -> str:
        return self.plan.status

    def track_id(self, i: int) -> str:
        return f"{self.incident_id}-T{i + 1}"

    def radar_ms(self) -> np.ndarray:
        """UTC epoch ms of every radar point of every track, sorted."""
        t = [r.plan.launch_ms + np.round(r.hits.t_s * 1000.0).astype(np.int64) for r in self.tracks]
        return np.sort(np.concatenate(t))


def group_incidents(results: list[FlightResult], world: World) -> list[Incident]:
    """Group drones into incidents and name them; sorted by incident id."""
    groups: dict[str, list[FlightResult]] = defaultdict(list)
    for r in results:
        groups[r.group].append(r)
    found = []
    for key, flights in groups.items():
        flights.sort(key=lambda r: int(r.plan.extra.get("drone", 0)))
        tracks = tuple(r for r in flights if r.detected)
        if not tracks:
            continue
        ms = np.concatenate([r.detection_ms() for r in flights])
        found.append((key, tuple(flights), tracks, int(ms.min()), int(ms.max())))
    ids = _incident_ids(found, world)
    out = [Incident(ids[k], k, f, t, a, b) for k, f, t, a, b in found]
    return sorted(out, key=lambda inc: inc.incident_id)


def _incident_ids(found, world: World) -> dict[str, str]:
    """Planted incidents keep their id; others get ``BASE-YYMMDD-HHMM`` of the first detection
    (local), with ``-2``, ``-3`` … on a clash. Ids never reveal the actor."""
    out: dict[str, str] = {}
    used: Counter[str] = Counter()
    for key, flights, _, _, _ in found:
        if flights[0].plan.incident_id:
            out[key] = flights[0].plan.incident_id
            used[out[key]] += 1
    rest = sorted((f for f in found if not f[1][0].plan.incident_id),
                  key=lambda f: (f[1][0].plan.installation_id, f[3], f[0]))  # fmt: skip
    for key, flights, _, start_ms, _ in rest:
        p = flights[0].plan
        first = utc_ms_to_local(start_ms, world.sites[p.installation_id].utc_offset_hours)
        base_id = f"{p.installation_id}-{first:%y%m%d-%H%M}"
        used[base_id] += 1
        out[key] = base_id if used[base_id] == 1 else f"{base_id}-{used[base_id]}"
    return out


def heard_only(results: list[FlightResult]) -> int:
    """Flights (groups) heard by RF or Remote ID but never seen by the radar: no incident."""
    by_group: dict[str, list[FlightResult]] = defaultdict(list)
    for r in results:
        by_group[r.group].append(r)
    return sum(
        1
        for rs in by_group.values()
        if not any(r.detected for r in rs) and any(len(r.rf) or len(r.rid) for r in rs)
    )
