"""Kinematics (SPEC §8.3, §8.5): timed reference paths flown with a point-mass model.

1. ``build_reference``: takeoff -> transit (to the entry point, then the nearest pattern point) ->
   pattern -> egress -> landing, as knots in *nominal* seconds. Random pauses (hover in place
   5-20 s, 0.08 per minute) are inserted on transit and egress legs only, never in the pattern.
2. ``sample_reference``: scale time by the flight's time warp ``w`` (durations × w, speeds ÷ w,
   shapes unchanged), sample at 10 Hz, add the smooth altitude noise (σ 3 m), and smooth with a
   2 s Gaussian so the reference has no instantaneous corners.
3. ``simulate``: all flights at once in numpy, one 10 Hz step at a time. Guidance tracks the
   reference (feed-forward velocity plus a pull back toward the reference point, D-025); air
   velocity follows it with a 1.5 s first-order lag, a 45°/s turn-rate cap, a 4 m/s climb cap and
   an air-speed cap; ground velocity = air velocity + 0.3 × wind (as of the current hour).

Output paths are region-frame meters at 1 Hz, starting at launch (``t_s = 0``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import lfilter

from kairos_defense.rng import rng_for
from kairos_defense.sim import formations
from kairos_defense.sim import patterns as pat
from kairos_defense.sim.calendar import Calendar
from kairos_defense.sim.plan import FlightPlan
from kairos_defense.sim.world import Site, World

DT = 0.1  # s, integration step (10 Hz)
COARSE_DT = 0.5  # s, grid the reference is smoothed on
TAU_S = 1.5  # velocity lag
TURN_CAP_DPS = 45.0
CLIMB_CAP_MS = 4.0
WIND_DRIFT = 0.3
KP_H = 0.3  # 1/s, horizontal pull toward the reference point
KP_Z = 0.4  # 1/s, vertical pull
VZ_NOMINAL = 2.8  # m/s nominal climb and descent: at most 4 m/s after warp (w >= 0.7)
SMOOTH_S = 2.0  # Gaussian σ applied to the sampled reference
ALT_NOISE_SIGMA = 3.0
ALT_NOISE_TAU_S = 30.0
ALT_NOISE_CLIP = 10.0
PAUSE_PER_MIN = 0.08
PAUSE_S = (5.0, 20.0)
PAUSE_JITTER_M = 1.0
SETTLE_S = 4.0  # keep simulating after the reference lands
VMAX_FACTOR = 1.3  # air-speed cap = 1.3 × cruise / w + 2 m/s
VMAX_MARGIN = 2.0
AIRBORNE_M = 0.5  # wind drift applies above this height
BATCH = 256

_COS_STEP = math.cos(math.radians(TURN_CAP_DPS * DT))
_SIN_STEP = math.sin(math.radians(TURN_CAP_DPS * DT))


class Phase(IntEnum):
    TAKEOFF = 0
    TRANSIT = 1
    PATTERN = 2
    EGRESS = 3
    LANDING = 4
    PAUSE = 5


CRUISE_PHASES = (Phase.TRANSIT, Phase.PATTERN, Phase.EGRESS, Phase.PAUSE)


@dataclass(frozen=True)
class Reference:
    """Timed reference in nominal seconds: knots ``(k, 3)`` and one phase per segment ``(k-1,)``."""

    t: np.ndarray
    xyz: np.ndarray
    phase: np.ndarray

    @property
    def duration_s(self) -> float:
        return float(self.t[-1])


@dataclass(frozen=True)
class Sampled:
    """A warped reference at 10 Hz: ``t`` (n,), ``pos`` and ``vel`` (n, 3), ``phase`` (n,)."""

    t: np.ndarray
    pos: np.ndarray
    vel: np.ndarray
    phase: np.ndarray


@dataclass(frozen=True)
class FlightPath:
    """A flown path at 1 Hz: ``t_s`` (n,) s after launch, ``xyz`` (n, 3) m, ``phase`` (n,) int8."""

    key: str
    t_s: np.ndarray
    xyz: np.ndarray
    phase: np.ndarray


# ------------------------------------------------------------------------------------- reference


def _durations(a: np.ndarray, b: np.ndarray, speed, vz: float, dur) -> np.ndarray:
    """Nominal segment durations ``(k,)`` from ``a`` to ``b`` (both ``(k, 3)``): the fixed
    ``dur`` where given, else the slower of horizontal distance ÷ speed and climb ÷ ``vz``."""
    dxy = np.hypot(b[:, 0] - a[:, 0], b[:, 1] - a[:, 1])
    with np.errstate(divide="ignore", invalid="ignore"):
        horiz = np.where(dxy > 0, dxy / speed, 0.0)
    moved = np.maximum(horiz, np.abs(b[:, 2] - a[:, 2]) / vz)
    return np.where(np.isnan(dur), moved, dur)


class _Knots:
    """Knots of a reference path, appended leg by leg."""

    def __init__(self, xyz) -> None:
        self.last = np.asarray(xyz, dtype=np.float64)
        self._p: list[np.ndarray] = [self.last[None, :]]
        self._d: list[np.ndarray] = []
        self._ph: list[np.ndarray] = []

    def _add(self, pts: np.ndarray, d: np.ndarray, phase) -> None:
        self._p.append(pts)
        self._d.append(d)
        self._ph.append(np.broadcast_to(np.asarray(phase, dtype=np.int8), (len(pts),)))
        self.last = pts[-1]

    def go(self, xyz, speed: float, phase: Phase, vz: float = VZ_NOMINAL, dur: float = math.nan):
        b = np.asarray(xyz, dtype=np.float64)[None, :]
        self._add(b, _durations(self.last[None, :], b, speed, vz, np.array([dur])), phase)

    def go_pausing(self, xyz, speed: float, phase: Phase, rng: np.random.Generator, on: bool):
        """Straight leg with Poisson pauses (hover in place with 1 m jitter, never in a pattern)."""
        a, b = self.last.copy(), np.asarray(xyz, dtype=np.float64)
        n = 0
        if on:
            nominal = math.hypot(b[0] - a[0], b[1] - a[1]) / speed
            n = int(rng.poisson(PAUSE_PER_MIN * nominal / 60.0))
        for f in np.sort(rng.random(n)) if n else []:
            q = a + f * (b - a)
            self.go(q, speed, phase)
            hold = rng.uniform(*PAUSE_S)
            secs = max(1, round(hold))
            pts = np.repeat(q[None, :], secs, axis=0)
            pts[:, :2] += rng.normal(0.0, PAUSE_JITTER_M, (secs, 2))
            self._add(pts, np.full(secs, hold / secs), Phase.PAUSE)
        self.go(b, speed, phase)

    def follow(self, path: pat.PatternPath, alt: float, phase: Phase) -> None:
        """Append a pattern; ``path.xy[0]`` must be the current point."""
        z = path.alt if path.alt is not None else np.full(len(path.xy), alt)
        pts = np.column_stack([path.xy, z])
        self._add(pts[1:], _durations(pts[:-1], pts[1:], path.speed, VZ_NOMINAL, path.dur), phase)

    def reference(self) -> Reference:
        d = np.concatenate(self._d)
        return Reference(np.r_[0.0, np.cumsum(d)], np.vstack(self._p), np.concatenate(self._ph))


def pattern_path(plan: FlightPlan, site: Site, rng: np.random.Generator) -> pat.PatternPath:
    """The plan's pattern geometry (§8.4), starting at the point nearest its entry point."""
    p = plan.pattern
    kind = p["type"]
    target = site.target(plan.target_kind)
    v = plan.cruise_ms
    launch = np.asarray(plan.launch_xy)
    if kind == "random_walk":
        t_up = plan.altitude_m / VZ_NOMINAL
        budget = p["duration_s"] - 2.0 * t_up
        cross = pat.fence_crossing_goal(site, launch) if p["cross_fence"] else None
        if cross is not None and 2.0 * np.hypot(*(cross - launch)) / v > 0.8 * budget:
            cross = None  # too slow to reach the fence and come back in time
        return pat.random_walk(launch, plan.recovery_xy, v, budget, cross, rng)
    approach = float(plan.approach_bearing_deg)
    entry = pat.entry_point(p, site, target, approach)
    c = target.centroid
    if kind == "orbit":
        return pat.orbit(c, p["radius_m"], p["direction"], p["laps"], p["angular_speed_dps"], entry)
    if kind == "lawnmower":
        axis = target.axis_bearing_deg
        return pat.lawnmower(c, axis, p["leg_m"], p["spacing_m"], p["legs"], v, entry)
    if kind == "figure8":
        return pat.figure8(c, target.axis_bearing_deg, p["lobe_radius_m"], p["loops"], v, entry)
    if kind == "perimeter":
        return pat.perimeter(site.fence, p["offset_m"], p["fraction"], v, entry)
    if kind == "hover":
        return pat.hover(c, p["dwell_s"], p["jitter_m"], rng)
    if kind == "transit_dips":
        return pat.transit_dips(
            site, target, approach, p["transit_alt_m"], p["dip_alt_m"], p["dips"], v
        )
    if kind == "choreography":  # a swarm's center (§8.7)
        return formations.centroid_path(p, c, entry, approach, v)
    raise ValueError(f"unknown pattern {kind!r}")


def build_reference(plan: FlightPlan, site: Site, rng: np.random.Generator) -> Reference:
    """Assemble the five flight phases into knots in nominal seconds (§8.3)."""
    p = plan.pattern
    v = plan.cruise_ms
    alt = float(p["transit_alt_m"]) if p["type"] == "transit_dips" else plan.altitude_m
    launch = np.r_[plan.launch_xy, 0.0]
    path = pattern_path(plan, site, rng)
    k = _Knots(launch)
    k.go(np.r_[plan.launch_xy, alt], v, Phase.TAKEOFF)
    if p["type"] != "random_walk":
        target = site.target(plan.target_kind).centroid
        entry = pat.entry_point(p, site, site.target(plan.target_kind), plan.approach_bearing_deg)
        if np.hypot(*(entry - target)) < np.hypot(*(launch[:2] - target)):
            k.go_pausing(np.r_[entry, alt], v, Phase.TRANSIT, rng, plan.pauses)
        start_z = path.alt[0] if path.alt is not None else alt
        k.go_pausing(np.r_[path.xy[0], start_z], v, Phase.TRANSIT, rng, plan.pauses)
    k.follow(path, alt, Phase.PATTERN)
    k.go_pausing(np.r_[plan.recovery_xy, alt], v, Phase.EGRESS, rng, plan.pauses)
    k.go(np.r_[plan.recovery_xy, 0.0], v, Phase.LANDING)
    return k.reference()


def altitude_noise(n_s: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth altitude wander at 1 Hz: OU process (σ 3 m, 30 s), clipped to ±10 m; ``(n_s,)``."""
    phi = math.exp(-1.0 / ALT_NOISE_TAU_S)
    eps = rng.normal(0.0, ALT_NOISE_SIGMA * math.sqrt(1.0 - phi * phi), n_s)
    return np.clip(lfilter([1.0], [1.0, -phi], eps), -ALT_NOISE_CLIP, ALT_NOISE_CLIP)


def _phase_at(ref: Reference, tk: np.ndarray, t: np.ndarray) -> np.ndarray:
    seg = np.clip(np.searchsorted(tk, t, side="right") - 1, 0, len(ref.phase) - 1)
    phase = ref.phase[seg].astype(np.int8)
    phase[t >= tk[-1]] = Phase.LANDING
    return phase


def sample_reference(ref: Reference, w: float, rng: np.random.Generator) -> Sampled:
    """Warp, add altitude noise in cruise phases, smooth (σ = 2 s) and sample at 10 Hz.

    Smoothing runs on a 2 Hz grid, then positions and velocities are interpolated to 10 Hz; with
    σ = 2 s nothing is lost and it is 25× cheaper than smoothing at 10 Hz.
    """
    tk = w * ref.t
    t_end = float(tk[-1])
    n = math.ceil((t_end + SETTLE_S) / DT) + 1
    t = np.arange(n) * DT
    tc = np.arange(0.0, t[-1] + COARSE_DT, COARSE_DT)
    pos = np.column_stack([np.interp(tc, tk, ref.xyz[:, i]) for i in range(3)])
    cruise = np.isin(_phase_at(ref, tk, tc), CRUISE_PHASES).astype(np.float64)
    mask = gaussian_filter1d(cruise, 5.0 / COARSE_DT, mode="nearest")
    noise = altitude_noise(math.ceil(tc[-1]) + 2, rng)
    pos[:, 2] += np.interp(tc, np.arange(len(noise)), noise) * mask
    pos = gaussian_filter1d(pos, SMOOTH_S / COARSE_DT, axis=0, mode="nearest")
    pos[:, 2] = np.maximum(pos[:, 2], 0.0)
    vel = np.gradient(pos, COARSE_DT, axis=0)
    fine_pos = np.column_stack([np.interp(t, tc, pos[:, i]) for i in range(3)])
    fine_vel = np.column_stack([np.interp(t, tc, vel[:, i]) for i in range(3)])
    return Sampled(t, fine_pos, fine_vel, _phase_at(ref, tk, t))


def vmax_for(plan: FlightPlan) -> float:
    """Air-speed cap for a flight (m/s): 1.3 × cruise ÷ w + 2 (D-025)."""
    return VMAX_FACTOR * plan.cruise_ms / plan.time_warp + VMAX_MARGIN


# ------------------------------------------------------------------------------------ simulation


def simulate(
    refs: list[Sampled], winds: list[np.ndarray], vmax: np.ndarray, stride: int = 10
) -> list[np.ndarray]:
    """Fly every reference; returns positions ``(n_i, 3)`` every ``stride`` steps (1 Hz at 10).

    ``winds[i]`` is the air velocity ``(len(refs[i].t), 2)`` m/s at each step. Flights are batched
    by length; each row is computed independently of the others in its batch.
    """
    out: list[np.ndarray | None] = [None] * len(refs)
    order = sorted(range(len(refs)), key=lambda i: (len(refs[i].t), i))
    for b0 in range(0, len(order), BATCH):
        idx = order[b0 : b0 + BATCH]
        res = _run_batch([refs[i] for i in idx], [winds[i] for i in idx], vmax[idx], stride)
        for i, r in zip(idx, res, strict=True):
            out[i] = r
    return out  # type: ignore[return-value]


def _pad(cols: list[np.ndarray], n: int, hold: bool) -> np.ndarray:
    """Stack 1-D arrays into ``(n, B)``, padding with the last value (``hold``) or zeros."""
    m = np.zeros((n, len(cols)))
    for j, c in enumerate(cols):
        m[: len(c), j] = c
        if hold:
            m[len(c) :, j] = c[-1]
    return m


def _run_batch(refs, winds, vmax, stride: int) -> list[np.ndarray]:
    n = max(len(r.t) for r in refs)
    rx, ry, rz = (_pad([r.pos[:, i] for r in refs], n, True) for i in range(3))
    vrx, vry, vrz = (_pad([r.vel[:, i] for r in refs], n, False) for i in range(3))
    wx, wy = (_pad([w[:, i] for w in winds], n, True) for i in range(2))
    x, y = rx[0].copy(), ry[0].copy()
    b = len(refs)
    z, vx, vy, vz = np.zeros(b), np.zeros(b), np.zeros(b), np.zeros(b)
    vmax2 = np.asarray(vmax, dtype=np.float64) ** 2
    a = DT / TAU_S
    n_out = (n - 1) // stride + 1
    rec = np.empty((n_out, b, 3))
    for k in range(n):
        if k % stride == 0:
            j = k // stride
            rec[j, :, 0], rec[j, :, 1], rec[j, :, 2] = x, y, z
        dx = vrx[k] + KP_H * (rx[k] - x)
        dy = vry[k] + KP_H * (ry[k] - y)
        dz = np.clip(vrz[k] + KP_Z * (rz[k] - z), -CLIMB_CAP_MS, CLIMB_CAP_MS)
        s2 = dx * dx + dy * dy
        over = s2 > vmax2
        if over.any():
            f = np.sqrt(vmax2[over] / s2[over])
            dx[over] *= f
            dy[over] *= f
        nx = vx + (dx - vx) * a
        ny = vy + (dy - vy) * a
        vz = vz + (dz - vz) * a
        na2 = vx * vx + vy * vy
        nb2 = nx * nx + ny * ny
        lim = (na2 > 0.25) & (vx * nx + vy * ny < _COS_STEP * np.sqrt(na2 * nb2))
        if lim.any():  # rotate the old velocity by the capped angle, keep the new speed
            ox, oy = vx[lim], vy[lim]
            s = np.where(ox * ny[lim] - oy * nx[lim] >= 0.0, 1.0, -1.0)
            f = np.sqrt(nb2[lim] / na2[lim])
            nx[lim] = (ox * _COS_STEP - s * oy * _SIN_STEP) * f
            ny[lim] = (s * ox * _SIN_STEP + oy * _COS_STEP) * f
        vx, vy = nx, ny
        air = z > AIRBORNE_M
        x = x + (vx + WIND_DRIFT * wx[k] * air) * DT
        y = y + (vy + WIND_DRIFT * wy[k] * air) * DT
        z = np.maximum(z + vz * DT, 0.0)
    return [rec[: (len(r.t) - 1) // stride + 1, i] for i, r in enumerate(refs)]


def fly(
    plans: list[FlightPlan],
    refs: list[Sampled],
    winds: list[np.ndarray],
) -> list[FlightPath]:
    """Simulate ``plans`` (with their sampled references and winds) and return 1 Hz paths."""
    vmax = np.array([vmax_for(p) for p in plans])
    pos = simulate(refs, winds, vmax, stride=10)
    out = []
    for p, r, xyz in zip(plans, refs, pos, strict=True):
        ph = r.phase[::10][: len(xyz)]
        out.append(FlightPath(p.key, np.arange(len(xyz), dtype=np.float64), xyz, ph))
    return out


def wind_along(plan: FlightPlan, cal: Calendar, t: np.ndarray) -> np.ndarray:
    """Air velocity ``(n, 2)`` m/s as of the hour, at ``t`` seconds after the plan's launch."""
    h0 = (plan.launch_local - cal.night_start_local(plan.night)).total_seconds() / 3600.0
    hours = np.floor(h0 + np.asarray(t) / 3600.0)
    return cal.wind_vectors(plan.region_id, cal.night_index(plan.night), hours)


def fly_plans(plans: list[FlightPlan], world: World, cal: Calendar, seed: int) -> list[FlightPath]:
    """Build, warp and fly every plan; each flight's draws come from streams named by its key."""
    refs, winds = [], []
    for p in plans:
        site = world.sites[p.installation_id]
        ref = build_reference(p, site, rng_for(seed, "flight", p.key, "path"))
        s = sample_reference(ref, p.time_warp, rng_for(seed, "flight", p.key, "altitude"))
        refs.append(s)
        winds.append(wind_along(p, cal, s.t))
    return fly(plans, refs, winds)
