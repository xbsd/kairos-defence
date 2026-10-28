"""Calendar (SPEC §8.2): nights, hourly weather, base events and public events.

A *night* is named by the local date of its evening and runs from 19:00 to 03:00 local. Times
inside a night are often given as minutes after the night start (19:00 -> 0, 01:00 -> 360).
Weather: wind speed has a Weibull(k = 2) marginal with mean 5 m/s, correlated hour to hour through a
Gaussian AR(1) copula; ``wind_dir_deg`` is the direction the wind blows *from* (D-023).
UTC conversions use the region's fixed ``utc_offset_hours`` (no daylight saving).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd
from scipy.special import ndtr

from kairos_defense import geo
from kairos_defense.config import Config
from kairos_defense.rng import rng_for
from kairos_defense.sim.world import World

_EPOCH = datetime(1970, 1, 1)
WIND_MEAN_MS = 5.0
WIND_SHAPE = 2.0
WIND_SCALE = WIND_MEAN_MS / math.gamma(1.0 + 1.0 / WIND_SHAPE)
WIND_HOURLY_RHO = 0.7
WIND_DIR_STEP_DEG = 10.0
VIS_RANGE_KM = (2.0, 15.0)
EXERCISE_P = 1.0 / 7.0  # about one per base per week
VIP_P = 1.0 / 30.0  # about one per base per month
SHIFT_CHANGE = time(22, 0)
SHIFT_CHANGE_MIN = 30
PUBLIC_EVENT_P = 0.3  # per public park per Friday or Saturday night
PUBLIC_KINDS = ("fair", "game", "concert", "market")


def local_to_utc_ms(local: datetime, utc_offset_hours: int) -> int:
    """Naive local datetime -> UTC epoch milliseconds (exact integer arithmetic)."""
    return (local - _EPOCH) // timedelta(milliseconds=1) - utc_offset_hours * 3_600_000


def utc_ms_to_local(ms: int, utc_offset_hours: int) -> datetime:
    return _EPOCH + timedelta(milliseconds=int(ms) + utc_offset_hours * 3_600_000)


def ms_to_ts(ms: np.ndarray) -> np.ndarray:
    """int64 epoch ms -> ``datetime64[ms]`` (UTC, naive), the dtype written to DuckDB."""
    return np.asarray(ms, dtype=np.int64).astype("datetime64[ms]")


def hhmm_to_night_min(hhmm: str, night_start: time) -> int:
    """``"HH:MM"`` local -> minutes after night start (earlier clock times: after midnight)."""
    h, m = (int(v) for v in hhmm.split(":"))
    out = h * 60 + m - (night_start.hour * 60 + night_start.minute)
    return out + 1440 if out < 0 else out


@dataclass(frozen=True)
class Calendar:
    nights: list[date]
    night_start: time  # 19:00
    night_len_min: int  # 480
    wind_ms: dict[str, np.ndarray]  # region -> (n_nights, n_hours)
    wind_dir_deg: dict[str, np.ndarray]  # region -> (n_nights, n_hours), blowing from
    vip_nights: dict[str, np.ndarray]  # installation -> (n_nights,) bool
    public_xy: dict[tuple[str, int], np.ndarray]  # (region, night index) -> (k, 2) event positions
    weather: pd.DataFrame
    base_events: pd.DataFrame
    public_events: pd.DataFrame

    def night_index(self, night: date) -> int:
        return (night - self.nights[0]).days

    def night_start_local(self, night: date) -> datetime:
        return datetime.combine(night, self.night_start)

    def wind_vectors(self, region_id: str, night_idx: np.ndarray, hours: np.ndarray) -> np.ndarray:
        """Air velocity (m/s, ENU) as of whole ``hours`` after the night start; ``(..., 2)``."""
        n_h = self.wind_ms[region_id].shape[1]
        h = np.clip(np.asarray(hours, dtype=np.int64), 0, n_h - 1)
        speed = self.wind_ms[region_id][night_idx, h]
        blows_to = self.wind_dir_deg[region_id][night_idx, h] + 180.0
        return speed[..., None] * geo.heading_vector(blows_to)

    def public_events_near(self, region_id: str, night_idx: int, xy, within_m: float):
        """Positions ``(k, 2)`` of public events that night within ``within_m`` of ``xy``."""
        pts = self.public_xy.get((region_id, night_idx))
        if pts is None or not len(pts):
            return np.zeros((0, 2))
        return pts[np.hypot(*(pts - np.asarray(xy)).T) <= within_m]


def build_calendar(cfg: Config, world: World, seed: int) -> Calendar:
    c = cfg.world.calendar
    n = (c.end_local - c.start_local).days + 1
    nights = [c.start_local + timedelta(days=i) for i in range(n)]
    start = time.fromisoformat(c.night_window_local[0])
    night_len = hhmm_to_night_min(c.night_window_local[1], start)
    n_hours = night_len // 60 + 1  # 19:00 ... 03:00 inclusive
    wind, wdir, wx_rows = {}, {}, []
    for region, offset in world.regions.items():
        sp, dr, vis = (np.empty((n, n_hours)) for _ in range(3))
        for i, night in enumerate(nights):
            sp[i], dr[i], vis[i] = _night_weather(
                rng_for(seed, "weather", region, night.isoformat()), n_hours
            )
        wind[region], wdir[region] = sp, dr
        t0 = np.array([local_to_utc_ms(datetime.combine(d, start), offset) for d in nights])
        ts = (t0[:, None] + np.arange(n_hours)[None, :] * 3_600_000).ravel()
        wx_rows.append(
            pd.DataFrame(
                {
                    "region_id": region,
                    "ts": ms_to_ts(ts),
                    "wind_ms": sp.ravel(),
                    "wind_dir_deg": dr.ravel(),
                    "visibility_km": vis.ravel(),
                }
            )
        )
    base_events, vip = _base_events(world, nights, seed)
    public_events, public_xy = _public_events(world, nights, start, seed)
    return Calendar(
        nights, start, night_len, wind, wdir, vip, public_xy,
        pd.concat(wx_rows, ignore_index=True), base_events, public_events,
    )  # fmt: skip


def _night_weather(rng: np.random.Generator, n_hours: int):
    """Hourly (wind m/s, wind-from deg, visibility km) for one region-night, METAR-rounded."""
    z = np.empty(n_hours)
    z[0] = rng.standard_normal()
    eps = rng.standard_normal(n_hours - 1)
    for h in range(1, n_hours):
        z[h] = WIND_HOURLY_RHO * z[h - 1] + math.sqrt(1.0 - WIND_HOURLY_RHO**2) * eps[h - 1]
    u = np.clip(ndtr(z), 1e-12, 1.0 - 1e-12)
    speed = WIND_SCALE * (-np.log1p(-u)) ** (1.0 / WIND_SHAPE)
    direction = rng.uniform(0.0, 360.0) + np.cumsum(
        np.r_[0.0, rng.normal(0.0, WIND_DIR_STEP_DEG, n_hours - 1)]
    )
    lo, hi = VIS_RANGE_KM
    vis = np.clip(
        rng.uniform(lo, hi) + np.cumsum(np.r_[0.0, rng.normal(0.0, 0.8, n_hours - 1)]), lo, hi
    )
    return np.round(speed, 1), geo.wrap360(np.round(direction)), np.round(vis, 1)


def _base_events(world: World, nights: list[date], seed: int):
    rows, vip = [], {}
    n = len(nights)
    for sid, site in world.sites.items():
        off = site.utc_offset_hours
        for d in nights:  # shift change, daily at 22:00 local
            t = local_to_utc_ms(datetime.combine(d, SHIFT_CHANGE), off)
            rows.append((sid, t, t + SHIFT_CHANGE_MIN * 60_000, "shift_change", "Shift change"))
        rng = rng_for(seed, "base_events", sid, "exercise")
        hit = rng.random(n) < EXERCISE_P
        start_min = rng.integers(17 * 12, 23 * 12, n) * 5  # 17:00-23:00, 5-minute steps
        dur_min = rng.integers(8, 25, n) * 15  # 2-6 h
        for i in np.flatnonzero(hit):
            t = (
                local_to_utc_ms(datetime.combine(nights[i], time()), off)
                + int(start_min[i]) * 60_000
            )
            rows.append((sid, t, t + int(dur_min[i]) * 60_000, "exercise", "Base exercise"))
        rng = rng_for(seed, "base_events", sid, "vip_visit")
        hit = rng.random(n) < VIP_P
        start_min = rng.integers(16 * 12, 21 * 12, n) * 5  # 16:00-21:00
        dur_min = rng.integers(16, 33, n) * 15  # 4-8 h: always overlaps that night
        for i in np.flatnonzero(hit):
            t = (
                local_to_utc_ms(datetime.combine(nights[i], time()), off)
                + int(start_min[i]) * 60_000
            )
            rows.append(
                (sid, t, t + int(dur_min[i]) * 60_000, "vip_visit", "Distinguished visitor")
            )
        vip[sid] = hit
    df = pd.DataFrame(rows, columns=["installation_id", "start_ts", "end_ts", "kind", "label"])
    df = df.sort_values(["installation_id", "start_ts", "kind"], kind="stable", ignore_index=True)
    df["start_ts"], df["end_ts"] = ms_to_ts(df.start_ts.to_numpy()), ms_to_ts(df.end_ts.to_numpy())
    return df, vip


def _public_events(world: World, nights: list[date], night_start: time, seed: int):
    rows, xy = [], {}
    weekend = np.array([d.weekday() in (4, 5) for d in nights])  # Friday and Saturday nights
    for park in world.parks:
        if park.base_id is not None:
            continue
        off = world.regions[park.region_id]
        rng = rng_for(seed, "public_events", park.park_id)
        n = len(nights)
        hit = weekend & (rng.random(n) < PUBLIC_EVENT_P)
        kind = rng.integers(0, len(PUBLIC_KINDS), n)
        start_min = rng.integers(17 * 4, 20 * 4, n) * 15  # 17:00-20:00
        dur_min = rng.integers(12, 21, n) * 15  # 3-5 h
        r = park.radius_m * np.sqrt(rng.random(n))
        pos = geo.destination(park.center, rng.uniform(0, 360, n), r)
        for i in np.flatnonzero(hit):
            t = (
                local_to_utc_ms(datetime.combine(nights[i], time()), off)
                + int(start_min[i]) * 60_000
            )
            k = PUBLIC_KINDS[kind[i]]
            label = f"{k.title()} at {park.park_id}"
            end = t + int(dur_min[i]) * 60_000
            rows.append((park.region_id, t, end, k, label, float(pos[i, 0]), float(pos[i, 1])))
            key = (park.region_id, int(i))
            xy[key] = np.vstack([xy.get(key, np.zeros((0, 2))), pos[i]])
    cols = ["region_id", "start_ts", "end_ts", "kind", "label", "x_m", "y_m"]
    df = pd.DataFrame(rows, columns=cols)
    df = df.sort_values(["region_id", "start_ts", "label"], kind="stable", ignore_index=True)
    df["start_ts"], df["end_ts"] = ms_to_ts(df.start_ts.to_numpy()), ms_to_ts(df.end_ts.to_numpy())
    return df, xy
