"""Sensors (SPEC §8.6). Phase 1: radar only (RF and Remote ID arrive in phase 2).

Radar, per scan at ``rate_hz``: the target is visible if within ``range_m`` (slant range from the
radar), at or above ``min_alt_m``, not inside the installation's terrain mask, not in a planted
outage and not in a dropout. A visible target is detected with probability falling linearly from
``p_detect_near`` at 0 m to ``p_detect_far`` at full range; that probability is the point's
``quality`` (D-027). Detected positions get ``N(0, pos_sigma_m + 0.004 × range)`` per axis and
``N(0, alt_sigma_m)`` in altitude. Dropouts follow a two-state Markov chain per second: 3% chance
per second of entering one, mean length 6 s (about 15% of seconds lost).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from kairos_defense.sim.kinematics import FlightPath
from kairos_defense.sim.world import Site

DROPOUT_ENTER_P = 0.03  # per second
DROPOUT_MEAN_S = 6.0
RANGE_NOISE_PER_M = 0.004


@dataclass(frozen=True)
class RadarHits:
    """Radar detections of one flight: ``t_s`` (m,) s after launch, ``xyz`` (m, 3) measured
    region meters, ``quality`` (m,) detection probability at that range."""

    sensor_id: str
    t_s: np.ndarray
    xyz: np.ndarray
    quality: np.ndarray

    def __len__(self) -> int:
        return len(self.t_s)


def dropout_up(n_s: int, rng: np.random.Generator) -> np.ndarray:
    """``(n_s,)`` bool, True where the radar holds the target; starts in the up state."""
    up = np.ones(n_s, dtype=bool)
    t = 0
    while t < n_s:
        ups = rng.geometric(DROPOUT_ENTER_P, 64)
        downs = rng.geometric(1.0 / DROPOUT_MEAN_S, 64)
        for u, d in zip(ups, downs, strict=True):
            t += int(u)
            if t >= n_s:
                break
            up[t : t + int(d)] = False
            t += int(d)
    return up


def radar_track(
    path: FlightPath,
    site: Site,
    rng: np.random.Generator,
    outage_s: tuple[float, float] | None = None,
) -> RadarHits:
    """Detect one flight with its installation's radar. Draws a fixed number of variates per scan,
    so the stream does not depend on what is visible."""
    radar = site.sensors["radar"]
    prm = radar.params
    period = 1.0 / float(prm["rate_hz"])
    t = np.arange(0.0, float(path.t_s[-1]) + 1e-9, period)
    xyz = np.column_stack([np.interp(t, path.t_s, path.xyz[:, i]) for i in range(3)])
    n = len(t)
    u = rng.random(n)
    noise_xy = rng.standard_normal((n, 2))
    noise_z = rng.standard_normal(n)
    up = dropout_up(int(np.ceil(t[-1])) + 1, rng)[np.floor(t).astype(np.int64)]

    dx, dy = xyz[:, 0] - radar.xy[0], xyz[:, 1] - radar.xy[1]
    slant = np.sqrt(dx * dx + dy * dy + xyz[:, 2] ** 2)
    visible = (slant <= radar.range_m) & (xyz[:, 2] >= prm["min_alt_m"])
    visible &= ~site.masked(xyz[:, :2], xyz[:, 2])
    if outage_s is not None:
        visible &= ~((t >= outage_s[0]) & (t <= outage_s[1]))
    frac = np.clip(slant / radar.range_m, 0.0, 1.0)
    p = prm["p_detect_near"] + (prm["p_detect_far"] - prm["p_detect_near"]) * frac
    hit = visible & up & (u < p)

    sigma = prm["pos_sigma_m"] + RANGE_NOISE_PER_M * slant
    meas = np.column_stack(
        [
            xyz[:, 0] + noise_xy[:, 0] * sigma,
            xyz[:, 1] + noise_xy[:, 1] * sigma,
            np.maximum(xyz[:, 2] + noise_z * prm["alt_sigma_m"], 0.0),
        ]
    )
    return RadarHits(radar.sensor_id, t[hit], meas[hit], np.round(p[hit], 4))
