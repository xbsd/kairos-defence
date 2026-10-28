"""Swarm choreography (SPEC §8.7) as pure geometry: formations, actions and their timeline.

Offsets live in the *swarm frame*: ``x'`` to the right of the swarm's heading and ``y'`` forward,
in meters. The frame is fixed to the travel heading at the start of the choreography (from the
entry point toward the target), so a formation is laid out relative to the approach and an action
transforms the current offsets (D-035):

- formation steps (``line_abreast``, ``v``, ``triangle``, ``trail``) blend from the current
  offsets to the new layout, then hold it;
- ``rotate`` turns the offsets by ``degrees`` (``cw`` adds to their bearing), ``expand`` scales
  them by ``factor``, ``split`` moves the first ``groups[0]`` drones and the rest apart by
  ``separation_m`` along ``x'`` (keeping the centroid), ``orbit_target`` leaves them unchanged.

Every change follows a smoothstep in time. Times are nominal seconds from the choreography start;
the flight's time warp is applied by the caller. ``centroid_path`` gives the swarm center's path:
a slow creep from the entry point toward the target during the steps before the first
``orbit_target``, a clockwise orbit at cruise speed during it, and a hold after it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from kairos_defense import geo
from kairos_defense.sim.patterns import ORBIT_STEP_DEG, PatternPath, _path

FORMATIONS = ("line_abreast", "v", "triangle", "trail")
ACTIONS = ("rotate", "expand", "split", "orbit_target")
V_HALF_ANGLE_DEG = 45.0
BLEND_MAX_FRAC = 0.6  # a formation change takes at most this share of its step ...
BLEND_MIN_S = 10.0  # ... and at least this long ...
BLEND_SPEED_MS = 5.0  # ... or as long as the farthest drone needs at this mean speed
ORBIT_DIRECTION = "cw"  # orbit_target has no direction in the config (D-035)


def formation(kind: str, n: int, spacing_m: float) -> np.ndarray:
    """Centered layout ``(n, 2)`` in the swarm frame; neighbors are ``spacing_m`` apart.

    ``line_abreast``: side by side across the heading. ``trail``: single file along it, drone 0
    in front. ``v``: drone 0 at the apex, the others alternating left and right along two arms at
    45° behind it. ``triangle``: rows of 1, 2, 3 … on an equilateral lattice, apex forward.
    """
    i = np.arange(n, dtype=np.float64)
    if kind == "line_abreast":
        xy = np.column_stack([(i - (n - 1) / 2.0) * spacing_m, np.zeros(n)])
    elif kind == "trail":
        xy = np.column_stack([np.zeros(n), -(i - (n - 1) / 2.0) * spacing_m])
    elif kind == "v":
        rank = np.ceil(i / 2.0)
        side = np.where(i % 2 == 1, -1.0, 1.0)
        a = math.radians(V_HALF_ANGLE_DEG)
        arm = rank * spacing_m
        xy = np.column_stack([side * arm * math.sin(a), -arm * math.cos(a)])
    elif kind == "triangle":
        pts, row = [], 0
        while len(pts) < n:
            for j in range(row + 1):
                pts.append(((j - row / 2.0) * spacing_m, -row * spacing_m * math.sqrt(3.0) / 2.0))
            row += 1
        xy = np.asarray(pts[:n], dtype=np.float64)
    else:
        raise ValueError(f"unknown formation {kind!r}")
    return xy - xy.mean(axis=0)


def resolve_steps(choreography, factors) -> list[dict]:
    """Config steps -> plain dicts ``{"kind", "duration_s", …}`` with each duration multiplied by
    its timing factor (the ±10% jitter of §8.7)."""
    out = []
    for step, f in zip(choreography, factors, strict=True):
        d = step.model_dump(exclude_none=True)
        kind = d.pop("formation", None) or d.pop("action")
        d["kind"] = kind
        d["duration_s"] = float(d["duration_s"]) * float(f)
        out.append(d)
    return out


def _smooth(u: np.ndarray) -> np.ndarray:
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def _after(step: dict, before: np.ndarray) -> np.ndarray:
    """Offsets at the end of ``step`` given the offsets at its start; ``(n, 2)``."""
    kind = step["kind"]
    if kind in FORMATIONS:
        return formation(kind, len(before), float(step["spacing_m"]))
    if kind == "rotate":
        sign = 1.0 if step["direction"] == "cw" else -1.0
        return geo.rotate(before, sign * float(step["degrees"]))
    if kind == "expand":
        return before * float(step["factor"])
    if kind == "split":
        n, n_a = len(before), int(step["groups"][0])
        shift = np.zeros_like(before)
        shift[:n_a, 0] = -float(step["separation_m"]) * (n - n_a) / n
        shift[n_a:, 0] = float(step["separation_m"]) * n_a / n
        return before + shift
    if kind == "orbit_target":
        return before.copy()
    raise ValueError(f"unknown choreography step {kind!r}")


@dataclass(frozen=True)
class Timeline:
    """A resolved choreography. ``start_s``/``end_s``/``blend_s`` are ``(k,)`` nominal seconds;
    ``keys`` ``(k + 1, n, 2)`` holds the offsets at every step boundary."""

    steps: tuple[dict, ...]
    start_s: np.ndarray
    end_s: np.ndarray
    blend_s: np.ndarray
    keys: np.ndarray

    @property
    def duration_s(self) -> float:
        return float(self.end_s[-1])

    @property
    def n(self) -> int:
        return int(self.keys.shape[1])

    def hold(self, i: int) -> tuple[float, float]:
        """Seconds during which formation step ``i`` holds its layout."""
        return float(self.start_s[i] + self.blend_s[i]), float(self.end_s[i])

    def offsets(self, t) -> np.ndarray:
        """Offsets ``(len(t), n, 2)`` in the swarm frame at nominal times ``t`` (s); before the
        start they are the first layout, after the end the last offsets."""
        t = np.atleast_1d(np.asarray(t, dtype=np.float64))
        out = np.broadcast_to(self.keys[0], (len(t), self.n, 2)).copy()
        out[t >= self.duration_s] = self.keys[-1]
        for i, step in enumerate(self.steps):
            m = (t >= self.start_s[i]) & (t < self.end_s[i])
            if not m.any():
                continue
            is_formation = step["kind"] in FORMATIONS
            span = self.blend_s[i] if is_formation else self.end_s[i] - self.start_s[i]
            s = _smooth((t[m] - self.start_s[i]) / span)[:, None, None]
            a, b = self.keys[i], self.keys[i + 1]
            if step["kind"] == "rotate":
                sign = 1.0 if step["direction"] == "cw" else -1.0
                ang = np.radians(sign * float(step["degrees"])) * s
                c, sn = np.cos(ang), np.sin(ang)
                x, y = a[None, :, 0:1], a[None, :, 1:2]
                out[m] = np.concatenate([x * c + y * sn, -x * sn + y * c], axis=2)
            else:
                out[m] = a + s * (b - a)
        return out


def timeline(steps: list[dict], n: int) -> Timeline:
    """Resolve ``steps`` (from ``resolve_steps``) for ``n`` drones. The first step must be a
    formation: it is the layout the swarm flies in before the choreography starts."""
    if not steps or steps[0]["kind"] not in FORMATIONS:
        raise ValueError("a choreography must start with a formation step")
    dur = np.array([float(s["duration_s"]) for s in steps])
    end = np.cumsum(dur)
    start = end - dur
    keys = [formation(steps[0]["kind"], n, float(steps[0]["spacing_m"]))]
    blend = np.zeros(len(steps))
    for i, s in enumerate(steps):
        keys.append(_after(s, keys[-1]))
        if s["kind"] in FORMATIONS:
            disp = float(np.max(np.hypot(*(keys[-1] - keys[-2]).T)))
            blend[i] = min(BLEND_MAX_FRAC * dur[i], max(BLEND_MIN_S, disp / BLEND_SPEED_MS))
    return Timeline(tuple(steps), start, end, blend, np.asarray(keys))


def to_region(offsets: np.ndarray, heading_deg: float) -> np.ndarray:
    """Swarm-frame offsets ``(..., 2)`` -> region-frame offsets for a swarm heading."""
    return geo.rotate(offsets, heading_deg)


def first_orbit_radius(steps: list[dict]) -> float:
    """Radius of the first ``orbit_target`` step, 0 if there is none."""
    return next((float(s["radius_m"]) for s in steps if s["kind"] == "orbit_target"), 0.0)


def centroid_path(
    pattern: dict, target_xy, entry_xy, approach_deg: float, cruise_ms: float
) -> PatternPath:
    """The swarm center's path during the choreography as a ``PatternPath`` with fixed nominal
    durations: creep from ``entry_xy`` to the orbit circle (or the target) over the steps before
    the first ``orbit_target``, orbit clockwise at ``cruise_ms`` during it, hold afterwards."""
    steps = pattern["steps"]
    target = np.asarray(target_xy, dtype=np.float64)
    entry = np.asarray(entry_xy, dtype=np.float64)
    work = geo.destination(target, approach_deg, first_orbit_radius(steps))
    first = next((i for i, s in enumerate(steps) if s["kind"] == "orbit_target"), len(steps))
    creep_s = sum(float(s["duration_s"]) for s in steps[:first])
    cur = entry if creep_s > 0 else work
    pts, durs, done = [cur], [], 0.0
    sign = 1.0 if ORBIT_DIRECTION == "cw" else -1.0
    for i, s in enumerate(steps):
        d = float(s["duration_s"])
        if s["kind"] == "orbit_target":
            rad = float(s["radius_m"])
            sweep = sign * math.degrees(cruise_ms * d / rad)
            m = max(2, math.ceil(abs(sweep) / ORBIT_STEP_DEG))
            b = float(geo.bearing(target, cur)) + sweep * np.arange(1, m + 1) / m
            arc = geo.destination(target, b, np.full(m, rad))
            pts += list(arc)
            durs += [d / m] * m
            cur = arc[-1]
        else:
            if i < first:
                done += d
                cur = entry + (work - entry) * (done / creep_s)
            pts.append(np.asarray(cur, dtype=np.float64).copy())
            durs.append(d)
    return _path(np.asarray(pts), np.nan, np.asarray(durs))


__all__ = [
    "ACTIONS",
    "FORMATIONS",
    "Timeline",
    "centroid_path",
    "first_orbit_radius",
    "formation",
    "resolve_steps",
    "timeline",
    "to_region",
]
