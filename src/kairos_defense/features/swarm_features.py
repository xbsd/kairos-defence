"""Swarm choreography descriptors (SPEC §14): detection, per-second descriptors, series, vectors.

A swarm incident is several radar tracks flown together. Each drone track is resampled to 1 Hz
(§9.1, ``resample``) and placed on the incident's common grid of whole seconds since its first
radar point. A second counts when at least ``swarm.min_drones`` drones have a position there.

Per second, and independent of drone order (D-148):

- ``centroid_x_rel_m``, ``centroid_y_rel_m``: the centroid, target-relative (the §9.2 target,
  chosen on the centroid path with ``choose_target``);
- ``centroid_speed_ms``: the centroid's speed, central difference (m/s);
- ``spread_m``: RMS distance of the drones to the centroid (m);
- ``pd_q25_m``, ``pd_q50_m``, ``pd_q75_m``: linear quartiles of the pairwise distances (m);
- ``axis_angle_deg``: the principal axis of the drone positions (PCA), as a bearing clockwise
  from north, unwrapped with period 180° (an axis has no head or tail);
- ``rot_rate_dps``: the axis's rate of turn, the derivative of ``axis_angle_deg`` averaged over
  a centered ``ROT_WINDOW_S`` window and clipped to ``ROT_CLIP_DPS`` (deg/s; clockwise
  positive).

The matching series is ``SERIES_COLUMNS`` z-normalized per channel; the prefilter vector is PAA
(``windows.paa_segments`` per channel, 6 × 16 = 96-d), L2-normalized. Detection (§14): at least
``min_drones`` tracks airborne together for ``min_duration_s`` consecutive seconds with every
pairwise distance under ``max_spacing_m``.

Pure functions over numpy and pandas; ``load_swarm`` reads raw points through the ``TrackStore``
port only, and only up to ``until_s`` (a live swarm never sees its future, rule 3, D-049).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import SiteGeometry, Target, choose_target, load_site
from kairos_defense.features.resample import epoch_seconds, resample
from kairos_defense.features.windows import fill_nan, paa_weights
from kairos_defense.ports import TrackStore

ROT_WINDOW_S = 5  # centered averaging window of the rotation rate (s)
ROT_CLIP_DPS = 20.0  # an ill-defined axis (near-round formation) cannot spike the series
SERIES_COLUMNS = ["spread_m", "pd_q25_m", "pd_q50_m", "pd_q75_m", "rot_rate_dps",
                  "centroid_speed_ms"]  # fmt: skip
DESCRIPTOR_COLUMNS = [
    "t_s",
    "n_drones",
    "centroid_x_rel_m",
    "centroid_y_rel_m",
    "centroid_speed_ms",
    "spread_m",
    "pd_q25_m",
    "pd_q50_m",
    "pd_q75_m",
    "axis_angle_deg",
    "rot_rate_dps",
]  # §7.2 swarm_features order, fmt: skip


@dataclass(frozen=True)
class SwarmFlight:
    """One swarm incident as observed up to ``until_s`` (None: its whole track).

    ``t_s`` (n,) int seconds since the incident's first radar point; ``positions`` (d, n, 3)
    float64 region meters (x, y, alt), NaN where a drone has no position; ``descriptors`` has
    ``DESCRIPTOR_COLUMNS`` for the seconds with at least ``min_drones`` drones.
    """

    incident_id: str
    installation_id: str
    region_id: str
    start_ts: pd.Timestamp  # first radar point of the incident, naive UTC
    track_ids: tuple[str, ...]
    t_s: np.ndarray
    positions: np.ndarray
    target: Target
    descriptors: pd.DataFrame
    is_swarm: bool  # §14 detection on the observed seconds
    together_s: int  # longest run of seconds flown together

    @property
    def n_drones(self) -> int:
        return len(self.track_ids)

    def relative_positions(self) -> np.ndarray:
        """``(d, n, 3)`` positions with x, y target-relative (meters)."""
        out = self.positions.copy()
        out[..., :2] -= np.asarray(self.target.centroid, dtype=np.float64)
        return out


def drone_grid(points: pd.DataFrame, max_gap_s: float) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Resample every track of one incident onto the common 1 Hz grid.

    ``points``: ``track_id``, ``ts`` (naive UTC), ``x_m``, ``y_m``, ``alt_m``, ``quality``.
    Returns ``(t_s (n,) int, track_ids, positions (d, n, 3))``; ``t_s`` counts from the first
    whole second at or after the incident's first point.
    """
    if len(points) == 0:
        return np.zeros(0, np.int64), [], np.zeros((0, 0, 3))
    s = epoch_seconds(points["ts"])
    t0, t1 = int(np.ceil(s.min())), int(np.floor(s.max()))
    n = max(t1 - t0 + 1, 0)
    tracks = sorted(points["track_id"].unique())
    pos = np.full((len(tracks), n, 3), np.nan)
    for d, tid in enumerate(tracks):
        f = resample(points[points["track_id"] == tid], max_gap_s)
        if len(f) == 0:
            continue
        idx = epoch_seconds(f["ts"]).round().astype(np.int64) - t0
        ok = (idx >= 0) & (idx < n)
        pos[d, idx[ok]] = f[["x_m", "y_m", "alt_m"]].to_numpy(dtype=np.float64)[ok]
    return np.arange(n, dtype=np.int64), list(tracks), pos


def pairwise_distances(xy: np.ndarray) -> np.ndarray:
    """``xy`` (n, d, 2) -> ``(n, d (d - 1) / 2)`` distances, NaN where either drone is missing."""
    d = xy.shape[1]
    i, j = np.triu_indices(d, k=1)
    return np.linalg.norm(xy[:, i, :] - xy[:, j, :], axis=2)


def longest_run(mask: np.ndarray) -> int:
    """Length of the longest run of True in a 1-D bool array."""
    best = cur = 0
    for v in np.asarray(mask, dtype=bool):
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def detect_swarm(
    xy: np.ndarray, min_drones: int, max_spacing_m: float, min_duration_s: float
) -> tuple[bool, int]:
    """§14 detection on ``xy`` (d, n, 2) region meters (NaN = no position): seconds where at least
    ``min_drones`` drones are present and every pairwise distance among them is under
    ``max_spacing_m``; a swarm when the longest run of such seconds lasts ``min_duration_s``.
    Returns ``(is_swarm, longest run in seconds)``."""
    if xy.ndim != 3 or xy.shape[0] < 2 or xy.shape[1] == 0:
        return False, 0
    per_t = np.transpose(xy, (1, 0, 2))  # (n, d, 2)
    present = np.isfinite(per_t).all(axis=2).sum(axis=1)
    pd_ = pairwise_distances(per_t)
    with np.errstate(invalid="ignore"):
        widest = np.where(np.isfinite(pd_), pd_, -np.inf).max(axis=1)
    together = (present >= min_drones) & (widest < max_spacing_m)
    run = longest_run(together)
    return bool(run >= min_duration_s), int(run)


def principal_axis_deg(rel: np.ndarray) -> np.ndarray:
    """``rel`` (n, d, 2) positions about their centroid -> (n,) principal-axis bearings in
    [0, 180) degrees clockwise from north (NaN where fewer than two drones are present)."""
    ok = np.isfinite(rel).all(axis=2)
    z = np.where(ok[..., None], rel, 0.0)
    cnt = ok.sum(axis=1).astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (z[..., 0] ** 2).sum(axis=1) / cnt
        syy = (z[..., 1] ** 2).sum(axis=1) / cnt
        sxy = (z[..., 0] * z[..., 1]).sum(axis=1) / cnt
        # major-axis angle from the x axis (east), counter-clockwise: 0.5 atan2(2 sxy, sxx - syy)
        theta = 0.5 * np.arctan2(2.0 * sxy, sxx - syy)
    bearing = np.mod(90.0 - np.degrees(theta), 180.0)
    bearing[cnt < 2] = np.nan
    return bearing


def unwrap_axis(deg: np.ndarray) -> np.ndarray:
    """Unwrap an axis angle (period 180°) through NaN gaps; NaN stays NaN."""
    out = np.full_like(deg, np.nan, dtype=np.float64)
    ok = np.isfinite(deg)
    if ok.any():
        out[ok] = np.degrees(np.unwrap(np.radians(deg[ok]) * 2.0) / 2.0)
    return out


def centered_mean(v: np.ndarray, window: int) -> np.ndarray:
    """Centered moving mean over ``window`` samples, ignoring NaN (NaN where all are NaN)."""
    s = pd.Series(v)
    return s.rolling(window, center=True, min_periods=1).mean().to_numpy(dtype=np.float64)


def swarm_descriptors(
    t_s: np.ndarray, positions: np.ndarray, target_xy: np.ndarray, min_drones: int
) -> pd.DataFrame:
    """Per-second descriptors (module docstring) for the seconds with at least ``min_drones``
    drones present. ``positions`` (d, n, 3) region meters; ``target_xy`` (2,) region meters."""
    xy = np.transpose(positions[..., :2], (1, 0, 2))  # (n, d, 2)
    present = np.isfinite(xy).all(axis=2)
    count = present.sum(axis=1)
    keep = count >= min_drones
    if not keep.any():
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in DESCRIPTOR_COLUMNS})
    xy, count, t = xy[keep], count[keep], np.asarray(t_s)[keep]
    with np.errstate(invalid="ignore"):
        c = np.nanmean(xy, axis=1)  # (m, 2)
        rel = xy - c[:, None, :]
        spread = np.sqrt(np.nanmean((rel**2).sum(axis=2), axis=1))
        pdist = pairwise_distances(xy)
        q = np.nanquantile(pdist, [0.25, 0.5, 0.75], axis=1)
    axis = unwrap_axis(principal_axis_deg(rel))
    tt = t.astype(np.float64)
    if len(tt) > 1:
        vx, vy = np.gradient(c[:, 0], tt), np.gradient(c[:, 1], tt)
        rot = np.gradient(axis, tt)
    else:
        vx = vy = rot = np.zeros(len(tt))
    rot = np.clip(centered_mean(rot, ROT_WINDOW_S), -ROT_CLIP_DPS, ROT_CLIP_DPS)
    target = np.asarray(target_xy, dtype=np.float64)
    return pd.DataFrame(
        {
            "t_s": t.astype(np.int32),
            "n_drones": count.astype(np.int32),
            "centroid_x_rel_m": c[:, 0] - target[0],
            "centroid_y_rel_m": c[:, 1] - target[1],
            "centroid_speed_ms": np.hypot(vx, vy),
            "spread_m": spread,
            "pd_q25_m": q[0],
            "pd_q50_m": q[1],
            "pd_q75_m": q[2],
            "axis_angle_deg": axis,
            "rot_rate_dps": rot,
        }
    )


def swarm_series(desc: pd.DataFrame) -> np.ndarray:
    """``(n, 6)`` float64 matching series (``SERIES_COLUMNS``), NaN filled by interpolation and
    z-normalized per channel; a constant channel becomes zeros."""
    raw = fill_nan(desc[SERIES_COLUMNS].to_numpy(dtype=np.float64))
    if len(raw) == 0:
        return raw
    mu, sd = raw.mean(axis=0), raw.std(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(sd > 1e-9, (raw - mu) / sd, 0.0)
    return z


def swarm_vector(series: np.ndarray, segments: int) -> np.ndarray:
    """PAA of each channel of ``series`` (n, c) into ``segments`` -> ``(c * segments,)`` float32,
    channel-major, L2-normalized (a zero vector stays zero)."""
    n = len(series)
    if n == 0:
        return np.zeros(series.shape[1] * segments, np.float32)
    paa = paa_weights(n, segments) @ series  # (segments, c)
    v = paa.T.reshape(-1)
    norm = float(np.linalg.norm(v))
    return (v / norm if norm > 0 else v).astype(np.float32)


def swarm_target(site: SiteGeometry, positions: np.ndarray) -> Target:
    """The §9.2 target chosen on the centroid path of ``positions`` (d, n, 3)."""
    with warnings.catch_warnings():  # seconds with no drone are NaN, not an error
        warnings.simplefilter("ignore", RuntimeWarning)
        c = np.nanmean(positions[..., :2], axis=0)  # (n, 2)
        alt = np.nanmean(positions[..., 2], axis=0)
    ok = np.isfinite(c).all(axis=1)
    if not ok.any():
        raise ValueError("cannot choose a target for a swarm with no positions")
    speed = np.full(len(c), np.nan)
    idx = np.flatnonzero(ok)
    if len(idx) > 1:
        sp = np.hypot(np.gradient(c[idx, 0], idx), np.gradient(c[idx, 1], idx))
        speed[idx] = sp
    else:
        speed[idx] = 0.0
    return choose_target(site, c, speed, alt)


def incident_points(store: TrackStore, incident_id: str) -> pd.DataFrame:
    """Every radar point of one incident, ordered by track and time (through the port)."""
    return store.sql(
        "SELECT track_id, ts, x_m, y_m, alt_m, quality FROM track_points "
        "WHERE incident_id = $i ORDER BY track_id, ts",
        {"i": incident_id},
    )


def build_flight(
    meta: dict, points: pd.DataFrame, site: SiteGeometry, scoring: ScoringConfig
) -> SwarmFlight:
    """A ``SwarmFlight`` from an incident row (``incident_id``, ``installation_id``,
    ``region_id``) and its points (already cut at the query second)."""
    sc = scoring.swarm
    t_s, tracks, pos = drone_grid(points, scoring.features.max_interp_gap_s)
    if len(t_s) == 0:
        raise ValueError(f"{meta['incident_id']}: no whole second to resample")
    target = swarm_target(site, pos)
    desc = swarm_descriptors(t_s, pos, np.asarray(target.centroid), sc.min_drones)
    ok, run = detect_swarm(pos[..., :2], sc.min_drones, sc.max_spacing_m, sc.min_duration_s)
    start = pd.Timestamp(points["ts"].min())
    return SwarmFlight(str(meta["incident_id"]), str(meta["installation_id"]),
                       str(meta["region_id"]), start, tuple(tracks), t_s, pos, target, desc,
                       ok, run)  # fmt: skip


def load_swarm(
    store: TrackStore, incident_id: str, scoring: ScoringConfig, until_s: float | None = None
) -> SwarmFlight:
    """One swarm incident as seen ``until_s`` seconds after its first radar point (None: all of
    it). Raises ``KeyError`` for an unknown incident."""
    inc = store.sql(
        "SELECT incident_id, installation_id, region_id, start_ts, n_tracks, is_swarm, status "
        "FROM incidents WHERE incident_id = $i",
        {"i": incident_id},
    )
    if len(inc) != 1:
        raise KeyError(f"unknown incident {incident_id!r}")
    meta = inc.iloc[0].to_dict()
    pts = incident_points(store, incident_id)
    if len(pts) == 0:
        raise ValueError(f"{incident_id}: no radar points")
    if until_s is not None:
        t0 = pd.Timestamp(pts["ts"].min())
        pts = pts[pts["ts"] <= t0 + pd.Timedelta(seconds=float(until_s))]
    site = load_site(store, str(meta["installation_id"]))
    return build_flight(meta, pts, site, scoring)
