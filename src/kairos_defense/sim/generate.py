"""Generation pipeline (SPEC §8.11): world -> calendar -> plans -> flights -> sensors -> incidents
-> paperwork -> tables.

``generate`` builds every table in memory; ``kairos-defense gen`` also writes the databases
(through ``kairos_defense.sim.writers``) and the data card. Single flights and swarm centers are
flown together by the §8.3 engine; each swarm drone is then derived from its center (§8.7). Every
drone is sensed by radar, RF and Remote ID; incidents group drones and span their detections by
any sensor (D-028, ``incidents``).
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from kairos_defense.config import Config
from kairos_defense.sim.actors import schedule
from kairos_defense.sim.calendar import Calendar, build_calendar
from kairos_defense.sim.incidents import FlightResult, Incident, group_incidents, sense
from kairos_defense.sim.kinematics import fly_plans
from kairos_defense.sim.paperwork import Paperwork, paperwork
from kairos_defense.sim.plan import FlightPlan
from kairos_defense.sim.scenario import LiveTiming, live_timing, p1_plans
from kairos_defense.sim.swarm import drone_paths, drone_plans, swarm_plans
from kairos_defense.sim.tables import build_tables
from kairos_defense.sim.world import World, build_world

log = logging.getLogger(__name__)

__all__ = ["FlightResult", "Generated", "Incident", "generate", "simulate"]


@dataclass
class Generated:
    seed: int
    world: World
    calendar: Calendar
    results: list[FlightResult]  # every drone flown
    incidents: list[Incident]
    incident_of: dict[str, str]  # flight key -> incident id (flights in an incident only)
    tables: dict[str, pd.DataFrame]
    truth: dict[str, pd.DataFrame]
    live: LiveTiming | None = None
    window: tuple[date, date] | None = None
    plans: list[FlightPlan] = field(default_factory=list)  # single flights and swarm centers
    paper: Paperwork | None = None
    notes: dict = field(default_factory=dict)


def all_plans(cfg: Config, world: World, cal: Calendar, seed: int) -> list[FlightPlan]:
    """Planted P1 flights plus every scheduled hobbyist, prober and copycat flight."""
    return p1_plans(cfg, world, seed) + schedule(cfg, world, cal, seed)


def fly_all(
    plans: list[FlightPlan], centers: list[FlightPlan], world: World, cal: Calendar, seed: int
) -> list[FlightResult]:
    """Fly single flights and swarm centers in one batch, derive the swarm drones, sense all."""
    paths = fly_plans(plans + centers, world, cal, seed)
    out = [sense(p, path, world, seed) for p, path in zip(plans, paths[: len(plans)], strict=True)]
    for c, path in zip(centers, paths[len(plans) :], strict=True):
        dpaths = drone_paths(c, path, seed)
        for dp, dpath in zip(drone_plans(c, dpaths), dpaths, strict=True):
            out.append(sense(dp, dpath, world, seed))
    return out


def simulate(plans: list[FlightPlan], world: World, cal: Calendar, seed: int) -> list[FlightResult]:
    """Fly and sense single-drone plans (no swarms)."""
    return fly_all(plans, [], world, cal, seed)


def _keep(plan: FlightPlan, nights: Collection[date] | None) -> bool:
    return nights is None or plan.night in nights


def _nights(window: tuple[date, date] | None, nights: Collection[date] | None):
    if nights is not None:
        return frozenset(nights)
    if window is None:
        return None
    return frozenset(window[0] + timedelta(days=i) for i in range((window[1] - window[0]).days + 1))


def generate(
    cfg: Config,
    seed: int | None = None,
    window: tuple[date, date] | None = None,
    nights: Collection[date] | None = None,
) -> Generated:
    """Build everything in memory. ``window`` (first night, last night) or ``nights`` limits the
    flights flown, for tests; scheduling always runs over the full calendar, so a window holds
    exactly the flights the full run has on those nights."""
    seed = cfg.world.seed if seed is None else seed
    world = build_world(cfg, seed)
    cal = build_calendar(cfg, world, seed)
    keep = _nights(window, nights)
    plans = [p for p in all_plans(cfg, world, cal, seed) if _keep(p, keep)]
    centers = [p for p in swarm_plans(cfg, world, cal, seed) if _keep(p, keep)]
    log.info("flying %d flights and %d swarm events", len(plans), len(centers))
    results = fly_all(plans, centers, world, cal, seed)
    incidents = group_incidents(results, world)
    incident_of = {r.plan.key: inc.incident_id for inc in incidents for r in inc.flights}
    paper = paperwork(cfg, world, incidents, seed)
    tables, truth = build_tables(incidents, results, world, cal, paper.tables)
    if keep is not None:
        tables = _trim_calendar(tables, cal, min(keep), max(keep))
    live = _live(cfg, results, incidents, world)
    span = (min(keep), max(keep)) if keep is not None else None
    return Generated(seed, world, cal, results, incidents, incident_of, tables, truth, live, span,
                     plans + centers, paper)  # fmt: skip


def _live(cfg: Config, results, incidents, world: World) -> LiveTiming | None:
    r = next((r for r in results if r.plan.key == cfg.scenario.live_incident), None)
    if r is None or not r.detected:
        return None
    inc = next(i for i in incidents if i.key == r.plan.key)
    first_any_s = (inc.start_ms - r.plan.launch_ms) / 1000.0
    return live_timing(r.plan, r.path.t_s, r.path.xyz[:, :2], r.hits.t_s, r.hits.xyz, world,
                       first_any_s)  # fmt: skip


def _trim_calendar(tables, cal: Calendar, first: date, last: date):
    """Keep calendar rows that fall between the first and last kept nights (tests only)."""
    lo = pd.Timestamp(cal.night_start_local(first)) - pd.Timedelta(hours=14)
    hi = pd.Timestamp(cal.night_start_local(last) + timedelta(days=1)) + pd.Timedelta(hours=14)
    out = dict(tables)
    w = tables["weather"]
    out["weather"] = w[(w.ts >= lo) & (w.ts < hi)].reset_index(drop=True)
    for t in ("base_events", "public_events"):
        df = tables[t]
        out[t] = df[(df.start_ts >= lo) & (df.start_ts < hi)].reset_index(drop=True)
    return out
