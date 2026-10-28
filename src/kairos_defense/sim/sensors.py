"""Sensors (SPEC §8.6): radar, RF and Remote ID. All three honor the terrain mask (D-003).

Radar, per scan at ``rate_hz``: the target is visible if within ``range_m`` (slant range from the
radar), at or above ``min_alt_m``, not inside the installation's terrain mask, not in a planted
outage and not in a dropout. A visible target is detected with probability falling linearly from
``p_detect_near`` at 0 m to ``p_detect_far`` at full range; that probability is the point's
``quality`` (D-027). Detected positions get ``N(0, pos_sigma_m + 0.004 × range)`` per axis and
``N(0, alt_sigma_m)`` in altitude. Dropouts follow a two-state Markov chain per second: 3% chance
per second of entering one, mean length 6 s (about 15% of seconds lost). Planted outages are
radar-only.

RF, per scan at ``rate_hz`` (0.5 Hz): while airborne, within ``range_m`` (slant) of the RF sensor
and not masked, one detection with the drone's protocol family, the band from the family number
(FAM-0x 2.4 GHz, FAM-1x 5.8 GHz, FAM-2x and FAM-3x 900 MHz), the bearing from the sensor plus
``N(0, bearing_sigma_deg)`` and an SNR of 40 dB at 100 m falling 20 dB per decade, plus
``N(0, 2 dB)`` (D-036).

Remote ID, at 1 Hz while airborne, within range and not masked: ``on`` broadcasts the drone's
stable serial and an operator position fixed within 10 m of the launch point; ``spoofed`` a new
random serial per flight and an operator position 1-3 km from the launch point; ``off`` nothing.
The broadcast drone position is the true position plus ``N(0, 2 m)`` (D-037).

Every scan draws a fixed number of variates, so what is visible never shifts a stream.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from kairos_defense import geo
from kairos_defense.rng import rng_for
from kairos_defense.sim.kinematics import AIRBORNE_M, FlightPath
from kairos_defense.sim.world import Site

DROPOUT_ENTER_P = 0.03  # per second
DROPOUT_MEAN_S = 6.0
RANGE_NOISE_PER_M = 0.004
SNR_REF_DB = 40.0  # RF SNR at SNR_REF_M
SNR_REF_M = 100.0
SNR_SIGMA_DB = 2.0
BANDS = {"0": "2.4GHz", "1": "5.8GHz", "2": "900MHz", "3": "900MHz"}
RID_OPERATOR_M = 10.0  # `on`: operator within this distance of the launch point
RID_SPOOF_M = (1000.0, 3000.0)  # `spoofed`: operator this far from the launch point
RID_POS_SIGMA_M = 2.0
RID_MODES = ("on", "off", "spoofed")


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


def _scan(path: FlightPath, rate_hz: float) -> tuple[np.ndarray, np.ndarray]:
    """Scan times ``(n,)`` s after launch at ``rate_hz`` and the true positions ``(n, 3)``."""
    t = np.arange(0.0, float(path.t_s[-1]) + 1e-9, 1.0 / float(rate_hz))
    return t, np.column_stack([np.interp(t, path.t_s, path.xyz[:, i]) for i in range(3)])


def _heard(site: Site, kind: str, xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Slant range ``(n,)`` from the site's ``kind`` sensor, and whether it hears the drone:
    airborne, within range and not masked; ``(n,)`` bool."""
    s = site.sensors[kind]
    dx, dy = xyz[:, 0] - s.xy[0], xyz[:, 1] - s.xy[1]
    slant = np.sqrt(dx * dx + dy * dy + xyz[:, 2] ** 2)
    ok = (xyz[:, 2] > AIRBORNE_M) & (slant <= s.range_m)
    return slant, ok & ~site.masked(xyz[:, :2], xyz[:, 2])


def rf_band(family: str) -> str:
    """Band of a protocol family (§8.6): ``FAM-0x`` 2.4 GHz, ``FAM-1x`` 5.8 GHz, else 900 MHz."""
    digit = family.removeprefix("FAM-")[:1]
    if digit not in BANDS:
        raise ValueError(f"unknown protocol family {family!r}")
    return BANDS[digit]


@dataclass(frozen=True)
class RfHits:
    """RF detections of one drone: ``t_s`` (m,) s after launch, ``bearing_deg`` (m,) from the RF
    sensor, ``snr_db`` (m,)."""

    sensor_id: str
    family: str
    band: str
    t_s: np.ndarray
    bearing_deg: np.ndarray
    snr_db: np.ndarray

    def __len__(self) -> int:
        return len(self.t_s)


def rf_track(path: FlightPath, site: Site, family: str, rng: np.random.Generator) -> RfHits:
    """Detect one drone's control link with its installation's RF sensor (§8.6)."""
    rf = site.sensors["rf"]
    t, xyz = _scan(path, rf.params["rate_hz"])
    n = len(t)
    noise_b, noise_s = rng.standard_normal(n), rng.standard_normal(n)
    slant, ok = _heard(site, "rf", xyz)
    brg = geo.wrap360(geo.bearing(rf.xy, xyz[:, :2]) + rf.params["bearing_sigma_deg"] * noise_b)
    snr = SNR_REF_DB - 20.0 * np.log10(np.maximum(slant, SNR_REF_M) / SNR_REF_M)
    snr = snr + SNR_SIGMA_DB * noise_s
    return RfHits(
        rf.sensor_id, family, rf_band(family), t[ok],
        np.round(brg[ok], 1) % 360.0, np.round(snr[ok], 1),
    )  # fmt: skip


def _serial(words: np.ndarray) -> str:
    """``SN-`` plus 16 upper-case hex digits from two 32-bit words."""
    return f"SN-{int(words[0]):08X}{int(words[1]):08X}"


def stable_serial(seed: int, actor_id: str, drone: int = 0) -> str:
    """The Remote ID serial of one drone; the same drone keeps it on every flight."""
    return _serial(rng_for(seed, "rid-serial", actor_id, str(drone)).integers(0, 2**32, 2))


@dataclass(frozen=True)
class RidHits:
    """Remote ID broadcasts received from one drone: ``t_s`` (m,), ``drone_xy`` (m, 2); the serial
    and the broadcast operator position are fixed for the flight."""

    sensor_id: str
    mode: str  # on | off | spoofed
    serial: str | None
    t_s: np.ndarray
    drone_xy: np.ndarray
    op_xy: np.ndarray  # (2,)

    def __len__(self) -> int:
        return len(self.t_s)


def rid_track(
    path: FlightPath, site: Site, mode: str, serial: str, launch_xy, rng: np.random.Generator
) -> RidHits:
    """Remote ID received by the installation's sensor (§8.6). ``serial`` is the drone's stable
    serial, used when ``mode == "on"``."""
    if mode not in RID_MODES:
        raise ValueError(f"unknown Remote ID mode {mode!r}")
    rid = site.sensors["rid"]
    # fixed draw order: operator offset (on), spoofed operator and serial, per-message noise
    r_on, b_on = RID_OPERATOR_M * np.sqrt(rng.random()), rng.uniform(0.0, 360.0)
    b_sp, d_sp = rng.uniform(0.0, 360.0), rng.uniform(*RID_SPOOF_M)
    spoof_serial = _serial(rng.integers(0, 2**32, 2))
    t, xyz = _scan(path, rid.params["rate_hz"])
    noise = rng.standard_normal((len(t), 2))
    launch = np.asarray(launch_xy, dtype=np.float64)
    if mode == "off":
        return RidHits(rid.sensor_id, mode, None, t[:0], np.zeros((0, 2)), launch)
    _, ok = _heard(site, "rid", xyz)
    if mode == "on":
        op, sn = geo.destination(launch, b_on, r_on), serial
    else:
        op, sn = geo.destination(launch, b_sp, d_sp), spoof_serial
    drone = np.round(xyz[ok, :2] + RID_POS_SIGMA_M * noise[ok], 1)
    return RidHits(rid.sensor_id, mode, sn, t[ok], drone, np.round(op, 1))
