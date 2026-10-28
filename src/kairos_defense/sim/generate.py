"""Generation pipeline (SPEC §8.11): world -> calendar -> plans -> flights -> radar -> tables.

``generate`` builds every table in memory; ``run`` also writes the databases (through
``kairos_defense.sim.writers``) and the data card. A flight that no sensor detects produces no
incident (D-003). An incident starts at its first detection and ends at its last; generated
incident ids are ``<BASE>-<YYMMDD>-<HHMM>`` of the first detection, local time (D-028).
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from kairos_defense.config import Config
from kairos_defense.rng import rng_for
from kairos_defense.sim.actors import schedule
from kairos_defense.sim.calendar import Calendar, build_calendar, ms_to_ts, utc_ms_to_local
from kairos_defense.sim.kinematics import FlightPath, fly_plans
from kairos_defense.sim.plan import FlightPlan
from kairos_defense.sim.scenario import LiveTiming, live_timing, p1_plans
from kairos_defense.sim.sensors import RadarHits, radar_track
from kairos_defense.sim.world import World, build_world
from kairos_defense.store.ddl import RAW_COLUMNS, TRUTH_COLUMNS

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FlightResult:
    plan: FlightPlan
    path: FlightPath  # truth, 1 Hz
    hits: RadarHits

    @property
    def detected(self) -> bool:
        return len(self.hits) > 0


@dataclass
class Generated:
    seed: int
    world: World
    calendar: Calendar
    results: list[FlightResult]
    incident_of: dict[str, str]  # flight key -> incident id (detected flights only)
    tables: dict[str, pd.DataFrame]
    truth: dict[str, pd.DataFrame]
    live: LiveTiming | None = None
    window: tuple[date, date] | None = None
    notes: dict = field(default_factory=dict)


def all_plans(cfg: Config, world: World, cal: Calendar, seed: int) -> list[FlightPlan]:
    """Planted P1 flights plus every scheduled hobbyist, prober and copycat flight."""
    return p1_plans(cfg, world, seed) + schedule(cfg, world, cal, seed)


def simulate(plans: list[FlightPlan], world: World, cal: Calendar, seed: int) -> list[FlightResult]:
    """Fly every plan and run its installation's radar; streams are named by the flight key."""
    paths = fly_plans(plans, world, cal, seed)
    out = []
    for plan, path in zip(plans, paths, strict=True):
        rng = rng_for(seed, "flight", plan.key, "radar")
        hits = radar_track(path, world.sites[plan.installation_id], rng, plan.outage_s)
        out.append(FlightResult(plan, path, hits))
    return out


def assign_incident_ids(results: list[FlightResult], world: World) -> dict[str, str]:
    """Planted flights keep their id; others get ``BASE-YYMMDD-HHMM`` of the first detection
    (local), with ``-2``, ``-3`` … on a clash. Ids never reveal the actor."""
    out: dict[str, str] = {}
    used: Counter[str] = Counter()
    det = [r for r in results if r.detected]
    for r in det:
        if r.plan.incident_id:
            out[r.plan.key] = r.plan.incident_id
            used[r.plan.incident_id] += 1
    order = sorted(
        (r for r in det if not r.plan.incident_id),
        key=lambda r: (r.plan.installation_id, r.plan.launch_ms + 1000 * r.hits.t_s[0], r.plan.key),
    )
    for r in order:
        off = world.sites[r.plan.installation_id].utc_offset_hours
        first = utc_ms_to_local(int(r.plan.launch_ms + 1000 * r.hits.t_s[0]), off)
        base_id = f"{r.plan.installation_id}-{first:%y%m%d-%H%M}"
        used[base_id] += 1
        out[r.plan.key] = base_id if used[base_id] == 1 else f"{base_id}-{used[base_id]}"
    return out


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=object) for c in columns})


def build_tables(
    results: list[FlightResult], incident_of: dict[str, str], world: World, cal: Calendar
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Raw tables (§7.1) and truth tables (§7.3), ordered by key and time."""
    det = sorted((r for r in results if r.detected), key=lambda r: incident_of[r.plan.key])
    inc_rows, tp_parts, tt_rows, path_parts = [], [], [], []
    for r in det:
        p, inc = r.plan, incident_of[r.plan.key]
        track = f"{inc}-T1"
        ts_ms = p.launch_ms + np.round(r.hits.t_s * 1000.0).astype(np.int64)
        inc_rows.append(
            (inc, p.installation_id, p.region_id, ts_ms[0], ts_ms[-1], 1, False, p.status)
        )
        n = len(ts_ms)
        tp_parts.append(
            pd.DataFrame(
                {
                    "incident_id": np.full(n, inc, dtype=object),
                    "track_id": np.full(n, track, dtype=object),
                    "installation_id": np.full(n, p.installation_id, dtype=object),
                    "region_id": np.full(n, p.region_id, dtype=object),
                    "sensor_id": np.full(n, r.hits.sensor_id, dtype=object),
                    "ts": ms_to_ts(ts_ms),
                    "x_m": r.hits.xyz[:, 0],
                    "y_m": r.hits.xyz[:, 1],
                    "alt_m": r.hits.xyz[:, 2],
                    "quality": r.hits.quality,
                }
            )
        )
        land = r.path.xyz[-1]
        tt_rows.append(
            (track, inc, p.actor_id, p.actor_type, p.launch_ms, p.time_warp,
             float(r.path.xyz[0, 0]), float(r.path.xyz[0, 1]), float(land[0]), float(land[1]))
        )  # fmt: skip
        m = len(r.path.t_s)
        path_parts.append(
            pd.DataFrame(
                {
                    "track_id": np.full(m, track, dtype=object),
                    "t_s": r.path.t_s,
                    "x_m": r.path.xyz[:, 0],
                    "y_m": r.path.xyz[:, 1],
                    "alt_m": r.path.xyz[:, 2],
                }
            )
        )
    incidents = pd.DataFrame(inc_rows, columns=RAW_COLUMNS["incidents"])
    incidents["start_ts"] = ms_to_ts(incidents.start_ts.to_numpy(np.int64))
    incidents["end_ts"] = ms_to_ts(incidents.end_ts.to_numpy(np.int64))
    incidents["n_tracks"] = incidents.n_tracks.astype("int32")
    incidents["is_swarm"] = incidents.is_swarm.astype(bool)
    track_truth = pd.DataFrame(tt_rows, columns=TRUTH_COLUMNS["track_truth"])
    track_truth["launch_ts"] = ms_to_ts(track_truth.launch_ts.to_numpy(np.int64))
    cols = RAW_COLUMNS["track_points"]
    raw = world.tables() | {
        "incidents": incidents,
        "track_points": pd.concat(tp_parts, ignore_index=True) if tp_parts else _empty(cols),
        "weather": cal.weather,
        "base_events": cal.base_events,
        "public_events": cal.public_events,
    }
    for t in ("rf_detections", "remote_id", "reports", "assessments"):  # phase 2
        raw[t] = _empty(RAW_COLUMNS[t])
    paths = pd.concat(path_parts, ignore_index=True) if path_parts else None
    truth = {
        "track_truth": track_truth,
        "true_paths": paths if paths is not None else _empty(TRUTH_COLUMNS["true_paths"]),
        "clue_truth": _empty(TRUTH_COLUMNS["clue_truth"]),
        "assessment_truth": _empty(TRUTH_COLUMNS["assessment_truth"]),
    }
    return {t: raw[t] for t in RAW_COLUMNS}, truth


def _in_window(plan: FlightPlan, window: tuple[date, date] | None) -> bool:
    return window is None or window[0] <= plan.night <= window[1]


def generate(
    cfg: Config, seed: int | None = None, window: tuple[date, date] | None = None
) -> Generated:
    """Build everything in memory. ``window`` (first night, last night) limits the flights flown,
    for tests; scheduling always runs over the full calendar, so a window holds exactly the
    flights the full run has on those nights."""
    seed = cfg.world.seed if seed is None else seed
    world = build_world(cfg, seed)
    cal = build_calendar(cfg, world, seed)
    plans = [p for p in all_plans(cfg, world, cal, seed) if _in_window(p, window)]
    log.info("flying %d flights", len(plans))
    results = simulate(plans, world, cal, seed)
    incident_of = assign_incident_ids(results, world)
    tables, truth = build_tables(results, incident_of, world, cal)
    if window is not None:
        tables = _trim_calendar(tables, cal, world, window)
    live = None
    for r in results:
        if r.plan.key == cfg.scenario.live_incident and r.detected:
            live = live_timing(r.plan, r.path.t_s, r.path.xyz[:, :2], r.hits.t_s, r.hits.xyz, world)
    return Generated(seed, world, cal, results, incident_of, tables, truth, live, window)


def _trim_calendar(tables, cal: Calendar, world: World, window: tuple[date, date]):
    """Keep calendar rows that fall on the window's nights (tests only)."""
    lo = pd.Timestamp(cal.night_start_local(window[0])) - pd.Timedelta(hours=14)
    hi = pd.Timestamp(cal.night_start_local(window[1]) + timedelta(days=1)) + pd.Timedelta(hours=14)
    out = dict(tables)
    for t in ("weather",):
        out[t] = tables[t][(tables[t].ts >= lo) & (tables[t].ts < hi)].reset_index(drop=True)
    for t in ("base_events", "public_events"):
        df = tables[t]
        out[t] = df[(df.start_ts >= lo) & (df.start_ts < hi)].reset_index(drop=True)
    return out
