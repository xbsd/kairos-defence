"""Planted scenario (SPEC §8.10, §6.4): the six P1 flights, flown by the normal engine.

Each P1 flight uses its stated base, launch time and time warp. ``jitter: none`` turns off the
launch, approach and radius jitter (and the random pauses, D-025); ``target_override`` changes the
target; ``sensor_outage_s`` is measured from launch (D-027); ``status: live`` marks the demo
incident. The planted swarm events are in ``swarm``; the planted DELTA report and wrong
assessment in ``reports`` and ``assessments``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from kairos_defense.config import Config
from kairos_defense.rng import rng_for
from kairos_defense.sim.actors import make_flight, prober_spec
from kairos_defense.sim.plan import FlightPlan
from kairos_defense.sim.world import World

ORBIT_TOL_M = 15.0  # §1.2: within 15 m of the orbit radius ...
ORBIT_HOLD_S = 10  # ... for 10 s


def p1_plans(cfg: Config, world: World, seed: int) -> list[FlightPlan]:
    """One plan per ``scenario_demo.yaml`` P1 flight; the key is the incident id."""
    spec = prober_spec(next(p for p in cfg.actors.probers if p.id == "P1"))
    plans = []
    for f in cfg.scenario.p1_flights:
        key = f.incident_id
        plans.append(
            make_flight(
                cfg,
                world,
                spec,
                key,
                f.base,
                f.start_local,
                rng_for(seed, "flight", key, "plan"),
                time_warp=f.time_warp,
                jitter=f.jitter != "none",
                target_override=f.target_override,
                incident_id=f.incident_id,
                status=f.status or "history",
                outage_s=tuple(f.sensor_outage_s) if f.sensor_outage_s else None,
            )
        )
    return plans


def orbit_established_s(
    t_s: np.ndarray, xy: np.ndarray, center, radius_m: float, after_s: float = 0.0
) -> float | None:
    """First time ``t >= after_s`` that starts 10 consecutive 1 Hz samples within 15 m of the
    orbit radius (§1.2); None if it never happens. ``t_s`` (n,), ``xy`` (n, 2)."""
    d = np.hypot(*(np.asarray(xy) - np.asarray(center)).T)
    ok = (np.abs(d - radius_m) <= ORBIT_TOL_M) & (np.asarray(t_s) >= after_s)
    if len(ok) < ORBIT_HOLD_S:
        return None
    run = np.convolve(ok.astype(np.int64), np.ones(ORBIT_HOLD_S, dtype=np.int64), "valid")
    hits = np.flatnonzero(run == ORBIT_HOLD_S)
    return float(t_s[hits[0]]) if len(hits) else None


@dataclass(frozen=True)
class LiveTiming:
    """§1.2 acceptance numbers for the live incident (T+0 = first radar contact)."""

    launch_local: datetime
    first_contact_local: datetime
    first_contact_after_launch_s: float
    first_contact_fence_m: float  # measured position's distance outside the fence
    orbit_established_s: float | None  # after first contact
    radar_lag_s: float = 0.0  # first radar contact minus first detection by any sensor (D-039)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def live_timing(
    plan: FlightPlan, t_s, true_xy, hit_t_s, hit_xy, world: World, first_any_s: float | None = None
) -> LiveTiming:
    """First contact and orbit-established time from the true path and radar hits of a flight.
    ``first_any_s`` is the first detection by any sensor, s after launch (default: the radar's)."""
    site = world.sites[plan.installation_id]
    t0 = float(hit_t_s[0])
    fence_m = float(site.fence_distance(np.asarray(hit_xy[:1]))[0])
    center = site.target(plan.target_kind).centroid
    est = orbit_established_s(t_s, true_xy, center, plan.pattern["radius_m"], after_s=t0)
    return LiveTiming(
        plan.launch_local,
        plan.launch_local + timedelta(seconds=t0),
        t0,
        fence_m,
        None if est is None else est - t0,
        0.0 if first_any_s is None else t0 - float(first_any_s),
    )
