"""Flight plans for hobbyists, probers and copycats (SPEC §6.3, §8.2, §8.5).

Probers and copycats share one plan builder, ``make_flight``: per-flight time warp in [0.7, 1.4],
launch jitter (uniform in a disc of ``jitter_m``), approach bearing ±10°, radius ±8%, altitude
uniform in the band and laps from the range. Launch points too close to the fence are pushed out
(D-005); P1 snaps its launch to County Rd 12 where the road is near (D-006). Copycats fly the
pattern, altitude and speed of the actor they mimic but approach from their own launch side
(D-026).

Streams: the schedule of actor ``A`` comes from ``rng_for(seed, A, "schedule")``; each flight's
plan from ``rng_for(seed, "flight", key, "plan")``. Hobbyist counts per base-night come from
``rng_for(seed, "hobbyists", base)``, one uniform per night.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
from scipy.stats import poisson

from kairos_defense import geo
from kairos_defense.config import Config
from kairos_defense.config.actors import Copycat, Launch, Prober
from kairos_defense.rng import rng_for
from kairos_defense.sim.calendar import Calendar, hhmm_to_night_min, local_to_utc_ms
from kairos_defense.sim.plan import FlightPlan
from kairos_defense.sim.world import World, nominal_launch, push_out, snap_to_road

TIME_WARP_RANGE = (0.7, 1.4)
APPROACH_JITTER_DEG = 10.0
RADIUS_JITTER = 0.08
RECOVERY_P1_M = 120.0
RECOVERY_OTHER_M = 300.0
VIP_WEIGHT = 3.0
PUBLIC_RATE_FACTOR = 2.0  # hobbyist rate doubles with a public event within 5 km (D-005)
PUBLIC_NEAR_RATE_M = 5000.0
PUBLIC_LAUNCH_M = 3000.0
PUBLIC_LAUNCH_P = 0.5  # share of hobbyists who launch from a public event within 3 km
HOBBYIST_WINDOW = ("19:00", "23:00")  # start time uniform in this local window (§8.2)


@dataclass(frozen=True)
class ActorSpec:
    """A prober, or a copycat resolved against the prober it mimics."""

    actor_id: str
    actor_type: str  # prober | copycat
    bases: list[str]
    flights: int | str
    target: str
    pattern: dict
    radius_range: tuple[float, float] | None  # copycat override for the orbit radius
    approach_bearing_deg: float
    launch: Launch
    altitude_m: tuple[float, float]
    cruise_ms: float
    rf_family: str
    rid: str | None  # on | off | spoofed; None = draw "on" with rid_on_prob
    rid_on_prob: float
    time_local: tuple[str, str]
    recovery_m: float


def prober_spec(p: Prober) -> ActorSpec:
    return ActorSpec(
        p.id, "prober", list(p.bases), p.flights, p.target, p.pattern.model_dump(), None,
        p.approach_bearing_deg, p.launch, tuple(p.altitude_m), p.cruise_speed_ms, p.rf_family,
        p.rid, 0.0, tuple(p.time_local), RECOVERY_P1_M if p.id == "P1" else RECOVERY_OTHER_M,
    )  # fmt: skip


def copycat_spec(c: Copycat, mimics: Prober) -> ActorSpec:
    radius = c.pattern_overrides.get("radius_m")
    return ActorSpec(
        c.id, "copycat", list(c.bases), c.flights, mimics.target, mimics.pattern.model_dump(),
        tuple(radius) if radius else None, c.launch.bearing_deg, c.launch,
        tuple(mimics.altitude_m), mimics.cruise_speed_ms, c.rf_family, None, c.rid_on_prob,
        tuple(c.time_local), RECOVERY_OTHER_M,
    )  # fmt: skip


def actor_specs(cfg: Config) -> list[ActorSpec]:
    probers = {p.id: p for p in cfg.actors.probers}
    specs = [prober_spec(p) for p in cfg.actors.probers]
    return specs + [copycat_spec(c, probers[c.mimics]) for c in cfg.actors.copycats]


def night_of(local: datetime) -> date:
    """The night a local time belongs to: before noon counts as the previous evening's night."""
    return (local - timedelta(days=1)).date() if local.hour < 12 else local.date()


def _disc(rng: np.random.Generator, radius: float) -> np.ndarray:
    """Uniform offset in a disc; ``(2,)``. Always draws two numbers."""
    r, b = radius * math.sqrt(rng.random()), rng.uniform(0.0, 360.0)
    return geo.destination((0.0, 0.0), b, r)


# ---------------------------------------------------------------------------- probers, copycats


def make_flight(
    cfg: Config,
    world: World,
    spec: ActorSpec,
    key: str,
    base: str,
    launch_local: datetime,
    rng: np.random.Generator,
    *,
    time_warp: float | None = None,
    jitter: bool = True,
    target_override: str | None = None,
    incident_id: str | None = None,
    status: str = "history",
    outage_s: tuple[float, float] | None = None,
) -> FlightPlan:
    """One prober or copycat flight (§8.5). Draws happen in a fixed order whatever the flags."""
    site = world.sites[base]
    target_kind = target_override or spec.target
    target = site.target(target_kind)
    # fixed draw order: warp, launch, approach, radius, altitude, pattern ints, recovery, rid
    w_draw = rng.uniform(*TIME_WARP_RANGE)
    launch_off = _disc(rng, spec.launch.jitter_m)
    approach_off = rng.uniform(-APPROACH_JITTER_DEG, APPROACH_JITTER_DEG)
    radius_u = rng.random()
    alt = float(rng.uniform(*spec.altitude_m))
    pattern = _resolve_pattern(spec, rng, radius_u, jitter)
    recovery_off = _disc(rng, spec.recovery_m)
    rid_u = rng.random()

    nominal = nominal_launch(site, target_kind, spec.launch.bearing_deg, spec.launch.distance_m)
    launch = nominal + (launch_off if jitter else 0.0)
    if spec.launch.snap_to_road:
        road = world.road(spec.launch.snap_to_road)
        if road.region_id == site.region_id:
            launch = snap_to_road(launch, road, nominal)
    launch = push_out(site.fence, target.centroid, launch)
    approach = float(geo.wrap360(spec.approach_bearing_deg + (approach_off if jitter else 0.0)))
    rid = spec.rid if spec.rid is not None else ("on" if rid_u < spec.rid_on_prob else "off")
    return FlightPlan(
        key=key,
        actor_id=spec.actor_id,
        actor_type=spec.actor_type,
        installation_id=base,
        region_id=site.region_id,
        night=night_of(launch_local),
        launch_local=launch_local,
        launch_ms=local_to_utc_ms(launch_local, site.utc_offset_hours),
        time_warp=float(time_warp if time_warp is not None else w_draw),
        pattern=pattern,
        target_kind=target_kind,
        launch_xy=(float(launch[0]), float(launch[1])),
        recovery_xy=(float(launch[0] + recovery_off[0]), float(launch[1] + recovery_off[1])),
        approach_bearing_deg=approach,
        altitude_m=alt,
        cruise_ms=float(spec.cruise_ms),
        rf_family=spec.rf_family,
        rid=rid,
        incident_id=incident_id,
        status=status,
        outage_s=outage_s,
        pauses=jitter,
    )


def _resolve_pattern(spec: ActorSpec, rng: np.random.Generator, radius_u: float, jitter: bool):
    """Per-flight pattern parameters: radius ±8% (or the copycat range), laps/loops/legs from
    their ranges, fraction and dwell uniform. Always consumes three draws."""
    p = dict(spec.pattern)
    kind = p["type"]
    u_int, u_a, u_b = rng.random(), rng.random(), rng.random()

    def pick(lo_hi) -> int:
        lo, hi = lo_hi
        return int(lo + min(int(u_int * (hi - lo + 1)), hi - lo))

    scale = 1.0 + RADIUS_JITTER * (2.0 * radius_u - 1.0) if jitter else 1.0
    if kind == "orbit":
        if spec.radius_range is not None:
            lo, hi = spec.radius_range
            p["radius_m"] = lo + (hi - lo) * radius_u
        else:
            p["radius_m"] = p["radius_m"] * scale
        p["laps"] = pick(p["laps"])
    elif kind == "figure8":
        p["lobe_radius_m"] = p["lobe_radius_m"] * scale
        p["loops"] = pick(p["loops"])
    elif kind == "lawnmower":
        p["legs"] = pick(p["legs"])
    elif kind == "perimeter":
        lo, hi = p["fraction"]
        p["fraction"] = lo + (hi - lo) * u_a
    elif kind == "hover":
        lo, hi = p["dwell_s"]
        p["dwell_s"] = lo + (hi - lo) * u_b
    return p


def schedule_actor(
    cfg: Config, world: World, cal: Calendar, seed: int, spec: ActorSpec
) -> list[FlightPlan]:
    """Spread ``spec.flights`` uniformly by month; base uniform; VIP nights weighted 3× (§8.2)."""
    if not isinstance(spec.flights, int) or spec.flights == 0:
        return []
    n = spec.flights
    months = sorted({(d.year, d.month) for d in cal.nights})
    by_month = {m: np.array([i for i, d in enumerate(cal.nights) if (d.year, d.month) == m])
                for m in months}  # fmt: skip
    lo = hhmm_to_night_min(spec.time_local[0], cal.night_start)
    hi = hhmm_to_night_min(spec.time_local[1], cal.night_start)
    rng = rng_for(seed, spec.actor_id, "schedule")
    plans = []
    for k in range(n):
        month = months[min(int((k + rng.random()) * len(months) / n), len(months) - 1)]
        base = spec.bases[int(rng.integers(len(spec.bases)))]
        idx = by_month[month]
        wts = 1.0 + (VIP_WEIGHT - 1.0) * cal.vip_nights[base][idx]
        night = cal.nights[int(rng.choice(idx, p=wts / wts.sum()))]
        offset_s = round(rng.uniform(lo * 60.0, hi * 60.0))
        launch_local = cal.night_start_local(night) + timedelta(seconds=offset_s)
        key = f"{spec.actor_id}/{k:03d}"
        plans.append(
            make_flight(
                cfg, world, spec, key, base, launch_local, rng_for(seed, "flight", key, "plan")
            )
        )
    return plans


# ----------------------------------------------------------------------------------- hobbyists


def hobbyist_plans(cfg: Config, world: World, cal: Calendar, seed: int) -> list[FlightPlan]:
    """Poisson(rate) flights per base-night from the base's park (or a nearby public event)."""
    h = cfg.actors.hobbyists
    lo = hhmm_to_night_min(HOBBYIST_WINDOW[0], cal.night_start) * 60.0
    hi = hhmm_to_night_min(HOBBYIST_WINDOW[1], cal.night_start) * 60.0
    plans = []
    for base, site in world.sites.items():
        park = world.park(site.park_id)
        near = [len(cal.public_events_near(site.region_id, i, site.origin, PUBLIC_NEAR_RATE_M))
                for i in range(len(cal.nights))]  # fmt: skip
        rate = h.rate_per_night_per_base * np.where(np.asarray(near) > 0, PUBLIC_RATE_FACTOR, 1.0)
        # one uniform per night, inverted through the Poisson CDF: a night's count depends only
        # on its own draw and rate
        u = rng_for(seed, "hobbyists", base).random(len(cal.nights))
        counts = poisson.ppf(u, rate).astype(np.int64)
        for i in np.flatnonzero(counts):
            night = cal.nights[i]
            events = cal.public_events_near(site.region_id, int(i), site.origin, PUBLIC_LAUNCH_M)
            t0 = cal.night_start_local(night)
            for j in range(int(counts[i])):
                key = f"H/{base}/{night.isoformat()}/{j}"
                rng = rng_for(seed, "flight", key, "plan")
                plans.append(_hobbyist(cfg, site, park, night, t0, j, key, events, (lo, hi), rng))
    return plans


def _hobbyist(cfg, site, park, night, night_start, j, key, events, window, rng) -> FlightPlan:
    h = cfg.actors.hobbyists
    start_s = round(rng.uniform(*window))
    duration = float(rng.uniform(*h.duration_s))
    alt = float(rng.uniform(*h.altitude_m))
    speed = float(rng.uniform(*h.speed_ms))
    rid = "on" if rng.random() < h.rid_on_prob else "off"
    fam = h.rf_families[int(rng.integers(len(h.rf_families)))]
    cross = bool(rng.random() < h.cross_fence_prob)
    use_event = (
        rng.random() < PUBLIC_LAUNCH_P and len(events) > 0 and "public_events" in h.launch_from
    )
    ev_idx = int(rng.integers(max(len(events), 1)))
    launch = park.center + _disc(rng, park.radius_m)
    if use_event:
        launch = np.asarray(events[ev_idx]) + _disc(rng, 50.0)
    launch = push_out(site.fence, site.origin, launch)
    recovery = launch + _disc(rng, RECOVERY_OTHER_M)
    launch_local = night_start + timedelta(seconds=start_s)
    return FlightPlan(
        key=key,
        actor_id=f"H-{site.installation_id}-{night:%y%m%d}-{j}",
        actor_type="hobbyist",
        installation_id=site.installation_id,
        region_id=site.region_id,
        night=night,
        launch_local=launch_local,
        launch_ms=local_to_utc_ms(launch_local, site.utc_offset_hours),
        time_warp=1.0,
        pattern={"type": "random_walk", "duration_s": duration, "cross_fence": cross},
        target_kind="fence",
        launch_xy=(float(launch[0]), float(launch[1])),
        recovery_xy=(float(recovery[0]), float(recovery[1])),
        approach_bearing_deg=None,
        altitude_m=alt,
        cruise_ms=speed,
        rf_family=fam,
        rid=rid,
    )


def schedule(cfg: Config, world: World, cal: Calendar, seed: int) -> list[FlightPlan]:
    """Every non-planted, non-swarm flight: hobbyists, probers P2-P6 and copycats."""
    plans = hobbyist_plans(cfg, world, cal, seed)
    for spec in actor_specs(cfg):
        plans += schedule_actor(cfg, world, cal, seed, spec)
    return plans
