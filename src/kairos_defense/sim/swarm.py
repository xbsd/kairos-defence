"""Swarms (SPEC §8.7): schedule, the swarm center's flight plan, and one path per drone.

A swarm event is flown as one *center* plan through the normal §8.3 engine: takeoff -> transit to
the entry point -> choreography (``formations.centroid_path``) -> egress -> landing. Each drone is
then ``center + offset + noise``: the offsets come from the choreography timeline, turned from the
swarm frame into the region frame by the swarm heading; the noise is a smooth wander with
σ = 2 m (OU, 10 s), faded in over the first 10 m of altitude (D-035). Each drone becomes its own
track in the incident.

Schedule (D-035): random events on random nights at the team's bases, launch uniform in
20:00-01:00 local; a team with a live planted event flies its random events only on later nights
(D-009). Planted events come from ``scenario_demo.yaml``. Every event draws its own time warp in
[0.7, 1.4], an approach bearing uniform in [0, 360), an altitude in the team band and a ±10%
factor per choreography step. Launch is 2 km from the target along the approach (pushed out of
the fence per D-005), recovery within 300 m of it, cruise 10 m/s. Swarms broadcast no Remote ID.

Streams: the schedule from ``rng_for(seed, team, "schedule")``; each event's plan from
``rng_for(seed, "flight", key, "plan")``; each drone's wander from
``rng_for(seed, "flight", key/Di, "wander")``.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta

import numpy as np
from scipy.signal import lfilter

from kairos_defense import geo
from kairos_defense.config import Config
from kairos_defense.config.actors import Swarm
from kairos_defense.rng import rng_for
from kairos_defense.sim import formations as fm
from kairos_defense.sim.actors import TIME_WARP_RANGE, disc_offset, night_of
from kairos_defense.sim.calendar import Calendar, hhmm_to_night_min, local_to_utc_ms
from kairos_defense.sim.kinematics import FlightPath, Phase
from kairos_defense.sim.plan import FlightPlan
from kairos_defense.sim.world import World, push_out

SWARM_CRUISE_MS = 10.0
LAUNCH_M = 2000.0
RECOVERY_M = 300.0
STEP_JITTER = 0.10
START_WINDOW = ("20:00", "01:00")
WANDER_SIGMA_M = 2.0
WANDER_TAU_S = 10.0
WANDER_RAMP_M = 10.0


def team(cfg: Config, team_id: str) -> Swarm:
    return next(s for s in cfg.actors.swarms if s.id == team_id)


def swarm_plan(
    cfg: Config,
    world: World,
    tm: Swarm,
    key: str,
    base: str,
    launch_local: datetime,
    rng: np.random.Generator,
    *,
    incident_id: str | None = None,
    status: str = "history",
) -> FlightPlan:
    """The center plan of one swarm event. Draws happen in a fixed order."""
    site = world.sites[base]
    target = site.target(tm.target)
    w = float(rng.uniform(*TIME_WARP_RANGE))
    approach = float(rng.uniform(0.0, 360.0))
    alt = float(rng.uniform(*tm.altitude_m))
    factors = rng.uniform(1.0 - STEP_JITTER, 1.0 + STEP_JITTER, len(tm.choreography))
    recovery_off = disc_offset(rng, RECOVERY_M)
    steps = fm.resolve_steps(tm.choreography, factors)
    launch = push_out(site.fence, target.centroid,
                      geo.destination(target.centroid, approach, LAUNCH_M))  # fmt: skip
    pattern = {
        "type": "choreography",
        "drones": tm.drones,
        "steps": steps,
        "radius_m": fm.first_orbit_radius(steps),
        "heading_deg": float(geo.wrap360(approach + 180.0)),
    }
    return FlightPlan(
        key=key,
        actor_id=tm.id,
        actor_type="swarm",
        installation_id=base,
        region_id=site.region_id,
        night=night_of(launch_local),
        launch_local=launch_local,
        launch_ms=local_to_utc_ms(launch_local, site.utc_offset_hours),
        time_warp=w,
        pattern=pattern,
        target_kind=tm.target,
        launch_xy=(float(launch[0]), float(launch[1])),
        recovery_xy=(float(launch[0] + recovery_off[0]), float(launch[1] + recovery_off[1])),
        approach_bearing_deg=approach,
        altitude_m=alt,
        cruise_ms=SWARM_CRUISE_MS,
        rf_family=tm.rf_family,
        rid="off",
        incident_id=incident_id,
        status=status,
        extra={"drones": tm.drones},
    )


def _random_nights(cfg: Config, cal: Calendar, tm: Swarm) -> np.ndarray:
    """Night indices a team's random events may use: after its live planted event, if any."""
    live = [night_of(s.start_local) for s in cfg.scenario.swarm_events
            if s.team == tm.id and s.status == "live"]  # fmt: skip
    idx = np.arange(len(cal.nights))
    if live:
        idx = idx[np.array([d > max(live) for d in cal.nights])]
    return idx


def swarm_plans(cfg: Config, world: World, cal: Calendar, seed: int) -> list[FlightPlan]:
    """Center plans of every swarm event: each team's random events, then the planted ones."""
    plans = []
    lo = hhmm_to_night_min(START_WINDOW[0], cal.night_start) * 60.0
    hi = hhmm_to_night_min(START_WINDOW[1], cal.night_start) * 60.0
    for tm in cfg.actors.swarms:
        nights = _random_nights(cfg, cal, tm)
        rng = rng_for(seed, tm.id, "schedule")
        for k in range(tm.random_events):
            night = cal.nights[int(nights[int(rng.integers(len(nights)))])]
            base = tm.bases[int(rng.integers(len(tm.bases)))]
            launch = cal.night_start_local(night) + timedelta(seconds=round(rng.uniform(lo, hi)))
            key = f"{tm.id}/{k:03d}"
            plans.append(
                swarm_plan(cfg, world, tm, key, base, launch, rng_for(seed, "flight", key, "plan"))
            )
    for ev in cfg.scenario.swarm_events:
        key = ev.incident_id
        plans.append(
            swarm_plan(
                cfg, world, team(cfg, ev.team), key, ev.base, ev.start_local,
                rng_for(seed, "flight", key, "plan"), incident_id=ev.incident_id,
                status=ev.status or "history",
            )
        )  # fmt: skip
    return plans


def choreography_clock(plan: FlightPlan, center: FlightPath) -> np.ndarray:
    """Nominal choreography seconds ``(n,)`` at each 1 Hz sample of the flown center path: 0 when
    the pattern phase starts, scaled back by the time warp."""
    started = np.flatnonzero(center.phase == Phase.PATTERN)
    t0 = float(center.t_s[started[0]]) if len(started) else 0.0
    return (center.t_s - t0) / plan.time_warp


def wander(n_s: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth per-drone position noise ``(n_s, 3)`` m: OU with σ 2 m and τ 10 s at 1 Hz,
    started from its stationary distribution."""
    phi = math.exp(-1.0 / WANDER_TAU_S)
    eps = rng.normal(0.0, WANDER_SIGMA_M * math.sqrt(1.0 - phi * phi), (n_s, 3))
    eps[0] = rng.normal(0.0, WANDER_SIGMA_M, 3)
    return lfilter([1.0], [1.0, -phi], eps, axis=0)


def drone_paths(plan: FlightPlan, center: FlightPath, seed: int) -> list[FlightPath]:
    """One true path per drone: flown center + choreography offset + wander (§8.7)."""
    p = plan.pattern
    tl = fm.timeline(p["steps"], int(p["drones"]))
    off = fm.to_region(tl.offsets(choreography_clock(plan, center)), p["heading_deg"])
    ramp = np.clip(center.xyz[:, 2] / WANDER_RAMP_M, 0.0, 1.0)[:, None]
    out = []
    for i in range(tl.n):
        key = f"{plan.key}/D{i}"
        noise = wander(len(center.t_s), rng_for(seed, "flight", key, "wander")) * ramp
        xyz = center.xyz.copy()
        xyz[:, :2] += off[:, i, :]
        xyz += noise
        xyz[:, 2] = np.maximum(xyz[:, 2], 0.0)
        out.append(FlightPath(key, center.t_s.copy(), xyz, center.phase.copy()))
    return out


def drone_plans(plan: FlightPlan, paths: list[FlightPath]) -> list[FlightPlan]:
    """Per-drone copies of a swarm plan: key ``<event>/D<i>``, launch and recovery where the
    drone took off and landed."""
    return [
        replace(
            plan,
            key=path.key,
            launch_xy=(float(path.xyz[0, 0]), float(path.xyz[0, 1])),
            recovery_xy=(float(path.xyz[-1, 0]), float(path.xyz[-1, 1])),
            extra={"swarm": plan.key, "drone": i, "drones": plan.extra["drones"]},
        )
        for i, path in enumerate(paths)
    ]
