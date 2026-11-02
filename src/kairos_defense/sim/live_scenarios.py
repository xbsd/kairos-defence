"""Live-mode scenarios (D-169, D-178): new, never-seen flights from the generator's functions.

A scenario is a named recipe: who flies (a known prober, a copycat, a hobbyist, a swarm team or an
invented operator), where, when on the live calendar (``LiveClock``, D-177) and with which seed.
``build`` plans and flies it with the §8 code (``actors.make_flight``, the hobbyist plan,
``swarm.swarm_plan``, ``drone_paths``, ``kinematics.fly_plans``, ``sensors.radar_track``,
``rf_track``, ``rid_track``) and turns what the sensors saw into time-ordered ingest messages
(``detections``): the columns of ``track_points``, ``rf_detections`` and ``remote_id`` plus an
opaque sensor track id. Nothing in a message names the actor; ``truth_rows`` holds who flew, for
``sim.writers`` only. Every draw comes from ``rng_for(seed, "live", …)`` or the flight's own
``rng_for(seed, "flight", key, …)`` streams, and the wind from the seed, not the date, so the same
seed and launch time of night fly the same flight on any live date (rule 4).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd

from kairos_defense.config import Config
from kairos_defense.config.actors import Launch
from kairos_defense.rng import rng_for
from kairos_defense.sim import actors, kinematics, swarm
from kairos_defense.sim.calendar import (
    Calendar,
    _night_weather,
    hhmm_to_night_min,
    local_to_utc_ms,
    utc_ms_to_local,
)
from kairos_defense.sim.incidents import FlightResult
from kairos_defense.sim.live_clock import LiveClock
from kairos_defense.sim.plan import FlightPlan
from kairos_defense.sim.sensors import radar_track, rf_track, rid_track, stable_serial
from kairos_defense.sim.world import World

SCENARIOS = ("returning-prober", "copycat", "hobbyist", "swarm-repeat", "new-operator-twice")
HOBBYIST_WINDOW = ("19:00", "23:00")
NEW_OPERATOR_WINDOW = ("19:00", "23:00")
SECOND_FLIGHT_GAP_S = 60.0  # after flight 1 has closed (idle_close_s), flight 2 launches
RESERVE_MARGIN_S = 60.0
KIND_ORDER = {"point": 0, "rf": 1, "rid": 2}
# The invented operator of `new-operator-twice` (D-178): a pattern, RF family and launch offset no
# configured actor uses.
NEW_OPERATOR = actors.ActorSpec(
    "N1", "new_operator", [], 0, "hq",
    {"type": "orbit", "radius_m": 260.0, "direction": "cw", "laps": [2, 2],
     "angular_speed_dps": 2.5},
    None, 45.0, Launch(bearing_deg=45.0, distance_m=1400.0, jitter_m=150.0), (70.0, 90.0), 12.0,
    "FAM-24", "off", 0.0, NEW_OPERATOR_WINDOW, actors.RECOVERY_OTHER_M,
)  # fmt: skip
NEW_OPERATOR_NICKNAME = "New operator (invented for live mode)"


class ScenarioError(ValueError):
    """A scenario, actor or base that cannot be flown (the message says what is allowed)."""


@dataclass(frozen=True)
class Flown:
    """One flight of a scenario: ``drones`` hold each drone's plan, true path and detections."""

    flight: int  # 1, or 2 for the second flight of new-operator-twice
    plan: FlightPlan  # the flight's (or swarm center's) plan
    drones: tuple[FlightResult, ...]


@dataclass
class Scenario:
    name: str
    actor_id: str
    actor_type: str
    nickname: str
    seed: int
    bases: tuple[str, ...]
    flights: list[Flown] = field(default_factory=list)

    @property
    def start_ms(self) -> int:
        return min(f.plan.launch_ms for f in self.flights)

    def detections(self) -> list[tuple[int, dict]]:
        """``(utc ms, ingest message)`` of every detection, in time order."""
        return detections(self)

    @property
    def end_ms(self) -> int:
        """The last detection of any drone (UTC ms)."""
        ends = [d.plan.launch_ms + round(float(t[-1]) * 1000)
                for f in self.flights for d in f.drones
                for t in (d.hits.t_s, d.rf.t_s, d.rid.t_s) if len(t)]  # fmt: skip
        return max(ends) if ends else self.start_ms

    def truth_rows(self) -> list[dict]:
        """Who flew each sensor track sent (for ``sim.writers`` only)."""
        rows = []
        for f in self.flights:
            for d in f.drones:
                if len(d.hits) == 0:
                    continue
                rows.append({"sensor_track_id": sensor_track_id(self.seed, d.plan.key,
                                                                d.plan.launch_ms),
                             "actor_id": self.actor_id, "actor_type": self.actor_type,
                             "nickname": self.nickname, "scenario": self.name,
                             "seed": int(self.seed), "base": d.plan.installation_id,
                             "flight": f.flight, "drone": int(d.plan.extra.get("drone", 0)),
                             "launch_ts": pd.Timestamp(d.plan.launch_ms, unit="ms")})  # fmt: skip
        return rows


def sensor_track_id(seed: int, key: str, launch_ms: int) -> str:
    """The radar's own id for a track: opaque, reproducible and unique per launch (the clock
    only moves forward), never naming the actor."""
    digest = hashlib.sha256(f"{seed}:{key}:{int(launch_ms)}".encode()).hexdigest()
    return "TRK-" + digest[:12].upper()


def iso_ms(ms: int) -> str:
    return pd.Timestamp(int(ms), unit="ms").strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ----------------------------------------------------------------------------- catalog


def catalog(cfg: Config) -> list[dict]:
    """The scenarios with their actor choices, bases and defaults (for the launcher)."""
    probers = [{"id": p.id, "nickname": p.nickname, "bases": list(p.bases)}
               for p in cfg.actors.probers]  # fmt: skip
    copycats = [{"id": c.id, "nickname": f"Copycat of {c.mimics}", "bases": list(c.bases)}
                for c in cfg.actors.copycats]  # fmt: skip
    teams = [{"id": s.id, "nickname": f"Swarm team {s.id}", "bases": list(s.bases)}
             for s in cfg.actors.swarms]  # fmt: skip
    every = list(cfg.world.installation_ids())
    return [
        {"name": "returning-prober", "title": "Returning prober", "actor_label": "Prober",
         "actors": probers, "default_actor": "P1", "allow_random": True, "bases": every,
         "second_base": False,
         "expectation": "A same-actor history flight in the top 3 by T+120 s"},
        {"name": "copycat", "title": "Copycat", "actor_label": "Copycat", "actors": copycats,
         "default_actor": "C1", "allow_random": False, "bases": every, "second_base": False,
         "expectation": "A same-actor history flight in the top 5 by T+120 s, above every "
                        "flight of the actor it mimics"},
        {"name": "hobbyist", "title": "Hobbyist", "actor_label": None, "actors": [],
         "default_actor": None, "allow_random": False, "bases": every, "second_base": False,
         "expectation": "No expectation on identity; the top score is reported"},
        {"name": "swarm-repeat", "title": "Swarm repeat", "actor_label": "Swarm team",
         "actors": teams, "default_actor": "S1", "allow_random": False, "bases": every,
         "second_base": False, "expectation": "The same team's past swarm event ranked first"},
        {"name": "new-operator-twice", "title": "New operator, twice", "actor_label": None,
         "actors": [], "default_actor": None, "allow_random": False, "bases": every,
         "second_base": True,
         "expectation": "Flight 1: no same-actor history exists. Flight 2: flight 1, learned "
                        "live, ranked first"},
    ]  # fmt: skip


def _choices(cfg: Config, name: str) -> dict[str, list[str]]:
    """Actor id -> the bases it may fly for one scenario."""
    if name == "returning-prober":
        return {p.id: list(p.bases) for p in cfg.actors.probers}
    if name == "copycat":
        return {c.id: list(c.bases) for c in cfg.actors.copycats}
    if name == "swarm-repeat":
        return {s.id: list(s.bases) for s in cfg.actors.swarms}
    return {}


def resolve(cfg: Config, name: str, actor: str | None, base: str | None,
            second_base: str | None, seed: int) -> tuple[str | None, str, str | None]:  # fmt: skip
    """Check and default ``(actor, base, second_base)``; raises ``ScenarioError``."""
    if name not in SCENARIOS:
        raise ScenarioError(f"unknown scenario {name!r}; use one of {', '.join(SCENARIOS)}")
    every = list(cfg.world.installation_ids())
    choices = _choices(cfg, name)
    if choices:
        default = next(e["default_actor"] for e in catalog(cfg) if e["name"] == name)
        if actor == "random" and name == "returning-prober":  # the seed picks who flies
            ids = sorted(a for a in choices if base is None or base in choices[a])
            if not ids:
                raise ScenarioError(f"{name}: no prober flies at {base}")
            actor = ids[int(rng_for(seed, "live", "actor").integers(len(ids)))]
        actor = actor or default
        if actor not in choices:
            raise ScenarioError(f"{name}: unknown actor {actor!r}; use one of "
                                f"{', '.join(sorted(choices))}")  # fmt: skip
        base = base or ("BRAVO" if "BRAVO" in choices[actor] else choices[actor][0])
        if base not in choices[actor]:
            raise ScenarioError(f"{name}: {actor} flies only at {', '.join(choices[actor])}, "
                                f"not {base}")  # fmt: skip
    else:
        if actor is not None:
            raise ScenarioError(f"{name} takes no actor")
        base = base or "BRAVO"
        if base not in every:
            raise ScenarioError(f"unknown base {base!r}; use one of {', '.join(every)}")
    if name == "new-operator-twice":
        if second_base is None:
            region = [b for b in every if _region(cfg, b) == _region(cfg, base)]
            second_base = region[(region.index(base) + 1) % len(region)]
        if second_base not in every or second_base == base:
            raise ScenarioError(f"second base must be another installation, not {second_base!r}")
    elif second_base is not None:
        raise ScenarioError(f"{name} flies at one base only")
    return actor, base, second_base


def _region(cfg: Config, base: str) -> str:
    return next(r.id for r in cfg.world.regions for i in r.installations if i.id == base)


# ----------------------------------------------------------------------------- building


def live_calendar(cfg: Config, world: World, nights: list, seed: int) -> Calendar:
    """A calendar for the live nights whose wind comes from the scenario seed and the night's
    position in the scenario, not its date (D-177). No events: the live calendar has none."""
    c = cfg.world.calendar
    start = time.fromisoformat(c.night_window_local[0])
    night_len = hhmm_to_night_min(c.night_window_local[1], start)
    n_hours = night_len // 60 + 1
    first = min(nights)
    n = (max(nights) - first).days + 1
    days = [first + timedelta(days=i) for i in range(n)]
    wind, wdir = {}, {}
    for region in world.regions:
        sp, dr = np.empty((n, n_hours)), np.empty((n, n_hours))
        for i in range(n):
            sp[i], dr[i], _ = _night_weather(rng_for(seed, "live", "weather", region, str(i)),
                                             n_hours)  # fmt: skip
        wind[region], wdir[region] = sp, dr
    empty = pd.DataFrame()
    return Calendar(days, start, night_len, wind, wdir, {}, {}, empty, empty, empty)


def _sense(plan: FlightPlan, path, world: World, seed: int, world_seed: int) -> FlightResult:
    """Radar, RF and Remote ID for one drone, each from its own stream; a known drone keeps its
    Remote ID serial (the world seed's, as in the history)."""
    site = world.sites[plan.installation_id]
    hits = radar_track(path, site, rng_for(seed, "flight", plan.key, "radar"), plan.outage_s)
    rf = rf_track(path, site, plan.rf_family, rng_for(seed, "flight", plan.key, "rf"))
    serial = stable_serial(world_seed, plan.actor_id, int(plan.extra.get("drone", 0)))
    rid = rid_track(path, site, plan.rid, serial, plan.launch_xy,
                    rng_for(seed, "flight", plan.key, "rid"))  # fmt: skip
    return FlightResult(plan, path, hits, rf, rid)


def _plan(cfg: Config, world: World, name: str, actor: str | None, base: str, key: str,
          launch_local: datetime, seed: int) -> tuple[FlightPlan, str, str]:  # fmt: skip
    """One flight's plan, its actor type and nickname."""
    rng = rng_for(seed, "live", "plan", key)
    if name == "returning-prober":
        p = next(p for p in cfg.actors.probers if p.id == actor)
        spec = actors.prober_spec(p)
        return (actors.make_flight(cfg, world, spec, key, base, launch_local, rng, status="live"),
                "prober", p.nickname)  # fmt: skip
    if name == "copycat":
        probers = {p.id: p for p in cfg.actors.probers}
        c = next(c for c in cfg.actors.copycats if c.id == actor)
        spec = actors.copycat_spec(c, probers[c.mimics])
        return (actors.make_flight(cfg, world, spec, key, base, launch_local, rng, status="live"),
                "copycat", f"Copycat of {c.mimics}")  # fmt: skip
    if name == "new-operator-twice":
        return (actors.make_flight(cfg, world, NEW_OPERATOR, key, base, launch_local, rng,
                                   status="live"),
                "new_operator", NEW_OPERATOR_NICKNAME)  # fmt: skip
    if name == "hobbyist":
        site = world.sites[base]
        plan = actors._hobbyist(
            cfg,
            site,
            world.park(site.park_id),
            actors.night_of(launch_local),
            launch_local,
            0,
            key,
            np.zeros((0, 2)),
            (0.0, 0.0),
            rng,
        )
        plan = replace(plan, actor_id=f"H-LIVE-{seed}", status="live")
        return plan, "hobbyist", "Hobbyist"
    tm = swarm.team(cfg, actor)
    plan = swarm.swarm_plan(cfg, world, tm, key, base, launch_local, rng, status="live")
    return plan, "swarm", f"Swarm team {tm.id}"


def _fly(cfg: Config, world: World, plan: FlightPlan, seed: int, flight: int) -> Flown:
    cal = live_calendar(cfg, world, [plan.night], seed)
    (path,) = kinematics.fly_plans([plan], world, cal, seed)
    if plan.actor_type != "swarm":
        return Flown(flight, plan, (_sense(plan, path, world, seed, cfg.world.seed),))
    paths = swarm.drone_paths(plan, path, seed)
    drones = swarm.drone_plans(plan, paths)
    return Flown(flight, plan, tuple(_sense(p, q, world, seed, cfg.world.seed)
                                     for p, q in zip(drones, paths, strict=True)))  # fmt: skip


def _window(cfg: Config, name: str, actor: str | None) -> tuple[str, str]:
    if name == "returning-prober":
        return tuple(next(p for p in cfg.actors.probers if p.id == actor).time_local)
    if name == "copycat":
        return tuple(next(c for c in cfg.actors.copycats if c.id == actor).time_local)
    if name == "swarm-repeat":
        return swarm.START_WINDOW
    return HOBBYIST_WINDOW if name == "hobbyist" else NEW_OPERATOR_WINDOW


def build(cfg: Config, world: World, clock: LiveClock, name: str, *, seed: int,
          actor: str | None = None, base: str | None = None,
          second_base: str | None = None) -> Scenario:  # fmt: skip
    """Plan and fly one scenario at the clock's next free time (the clock is not moved)."""
    actor, base, second_base = resolve(cfg, name, actor, base, second_base, seed)
    site = world.sites[base]
    launch = clock.launch_local(site.utc_offset_hours, _window(cfg, name, actor))
    key = f"LIVE/{name}/{actor or name}/{base}/{seed}/1"  # names streams; hashed into track ids
    plan, kind, nickname = _plan(cfg, world, name, actor, base, key, launch, seed)
    sc = Scenario(name, actor or plan.actor_id, kind, nickname, int(seed),
                  (base,) + ((second_base,) if second_base else ()))  # fmt: skip
    sc.flights.append(_fly(cfg, world, plan, seed, 1))
    if second_base:
        gap = cfg.scoring.live.idle_close_s + SECOND_FLIGHT_GAP_S
        after = sc.end_ms + round(gap * 1000)
        site2 = world.sites[second_base]
        launch2 = utc_ms_to_local(after, site2.utc_offset_hours).replace(microsecond=0)
        launch2 += timedelta(seconds=1)
        key2 = f"LIVE/{name}/{actor or name}/{base}/{seed}/2"
        plan2, _, _ = _plan(cfg, world, name, actor, second_base, key2, launch2, seed)
        sc.flights.append(_fly(cfg, world, plan2, seed, 2))
    return sc


def reserve_until(sc: Scenario, cfg: Config) -> int:
    """The clock value after this scenario: its last detection + idle close + a margin."""
    return sc.end_ms + round((cfg.scoring.live.idle_close_s + RESERVE_MARGIN_S) * 1000)


# ----------------------------------------------------------------------------- detections


def _f(v: float) -> float:
    return round(float(v), 3)


def detections(sc: Scenario) -> list[tuple[int, dict]]:
    out: list[tuple[int, dict]] = []
    for f in sc.flights:
        for d in f.drones:
            p, inst = d.plan, d.plan.installation_id
            tid = sensor_track_id(sc.seed, p.key, p.launch_ms)
            for t, xyz, q in zip(d.hits.t_s, d.hits.xyz, d.hits.quality, strict=True):
                ms = p.launch_ms + round(float(t) * 1000)
                out.append((ms, {"v": 1, "type": "point", "installation_id": inst,
                                 "sensor_id": d.hits.sensor_id, "sensor_track_id": tid,
                                 "ts": iso_ms(ms), "x_m": _f(xyz[0]), "y_m": _f(xyz[1]),
                                 "alt_m": _f(xyz[2]), "quality": _f(q)}))  # fmt: skip
            for t, b, s in zip(d.rf.t_s, d.rf.bearing_deg, d.rf.snr_db, strict=True):
                ms = p.launch_ms + round(float(t) * 1000)
                out.append((ms, {"v": 1, "type": "rf", "installation_id": inst,
                                 "sensor_id": d.rf.sensor_id, "ts": iso_ms(ms),
                                 "band": d.rf.band, "protocol_family": d.rf.family,
                                 "bearing_deg": _f(b), "snr_db": _f(s)}))  # fmt: skip
            for t, xy in zip(d.rid.t_s, d.rid.drone_xy, strict=True):
                ms = p.launch_ms + round(float(t) * 1000)
                out.append((ms, {"v": 1, "type": "rid", "installation_id": inst, "ts": iso_ms(ms),
                                 "serial": d.rid.serial, "drone_x_m": _f(xy[0]),
                                 "drone_y_m": _f(xy[1]), "op_x_m": _f(d.rid.op_xy[0]),
                                 "op_y_m": _f(d.rid.op_xy[1])}))  # fmt: skip
    out.sort(key=lambda m: (m[0], KIND_ORDER[m[1]["type"]], m[1].get("sensor_id", ""),
                            m[1].get("sensor_track_id") or m[1].get("serial") or ""))  # fmt: skip
    return out


def launch_utc_ms(local: datetime, utc_offset_hours: int) -> int:
    return local_to_utc_ms(local, utc_offset_hours)
