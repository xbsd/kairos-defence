"""Target choice, target-relative frame and matching channels (SPEC §9.2, §9.3).

The target is the installation asset, or the fence as a pseudo-asset, where the drone lingers: the
smallest *median* distance over the slowest 50% of its in-flight seconds (takeoff and landing
excluded) within 500 m of the fence (D-046; the spec's mean over all of the slowest seconds picks
the fence for P1 at ALPHA, where takeoff and landing are seen 2 km out). For an asset, distance is
to its polygon (0 inside); for the fence it is to the fence line. Target-relative coordinates
shift the region frame so the target centroid is the origin (no rotation), so tracks at different
bases line up.

Channels per second: ``speed_ms``, ``turn_rate_dps``, ``dist_target_m``, ``alt_m``, ``vspeed_ms``.
Before any comparison each channel is z-normalized over the series being compared (σ floor 1e-3)
and multiplied by its weight from ``scoring.yaml``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import shapely
from shapely import wkt
from shapely.geometry import Polygon

from kairos_defense import geo
from kairos_defense.config import ScoringConfig
from kairos_defense.features.resample import resample
from kairos_defense.ports import TrackStore

SIGMA_FLOOR = 1e-3
CRUISE_ALT_FRACTION = 0.8  # takeoff/landing: leading/trailing seconds below 0.8 x median altitude
NEAR_FENCE_M = 500.0  # target choice uses seconds within this distance of the fence (0 inside)
MIN_NEAR_S = 10  # fewer near seconds than this: use every in-flight second


@dataclass(frozen=True)
class Target:
    """An asset rectangle, or the fence pseudo-asset (``kind == "fence"``), in region meters."""

    asset_id: str
    kind: str
    polygon: Polygon
    centroid: np.ndarray  # (2,)

    @property
    def radius_m(self) -> float:
        """Radius of the circle with the target's area (m)."""
        return float(np.sqrt(self.polygon.area / np.pi))

    def distance(self, xy: np.ndarray) -> np.ndarray:
        """Distance (m) from points ``(n, 2)`` to the target: to the polygon (0 inside) for an
        asset, to the fence line for the fence. NaN rows stay NaN."""
        xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
        out = np.full(len(xy), np.nan)
        ok = np.isfinite(xy).all(axis=1)
        geom = self.polygon.exterior if self.kind == "fence" else self.polygon
        if ok.any():
            out[ok] = shapely.distance(shapely.points(xy[ok]), geom)
        return out


@dataclass(frozen=True)
class SiteGeometry:
    """One installation's candidate targets (assets in id order, then the fence)."""

    installation_id: str
    region_id: str
    utc_offset_hours: int
    targets: tuple[Target, ...]
    fence: Polygon

    def target(self, asset_id: str) -> Target:
        for t in self.targets:
            if t.asset_id == asset_id:
                return t
        raise KeyError(f"{self.installation_id}: no target {asset_id!r}")


def site_from_rows(installation: dict, assets: pd.DataFrame, utc_offset_hours: int) -> SiteGeometry:
    """Build a site from one ``installations`` row and its ``assets`` rows (SPEC §7.1)."""
    targets = [
        Target(
            str(a.asset_id),
            str(a.kind),
            wkt.loads(a.polygon_wkt),
            np.array([a.centroid_x_m, a.centroid_y_m], dtype=np.float64),
        )
        for a in assets.sort_values("asset_id").itertuples()
    ]
    fence = wkt.loads(installation["fence_wkt"])
    inst = installation["installation_id"]
    c = np.asarray(fence.centroid.coords[0], dtype=np.float64)
    targets.append(Target(f"{inst}-fence", "fence", fence, c))
    return SiteGeometry(inst, installation["region_id"], int(utc_offset_hours), tuple(targets),
                        fence)  # fmt: skip


def load_site(store: TrackStore, installation_id: str) -> SiteGeometry:
    """Read one installation's geometry through the ``TrackStore`` port."""
    inst = store.sql(
        "SELECT i.installation_id, i.region_id, i.fence_wkt, r.utc_offset_hours "
        "FROM installations i JOIN regions r USING (region_id) WHERE installation_id = $id",
        {"id": installation_id},
    )
    if len(inst) != 1:
        raise KeyError(f"unknown installation {installation_id!r}")
    assets = store.sql("SELECT * FROM assets WHERE installation_id = $id", {"id": installation_id})
    row = inst.iloc[0].to_dict()
    return site_from_rows(row, assets, int(row["utc_offset_hours"]))


def in_flight_mask(alt_m: np.ndarray) -> np.ndarray:
    """False on takeoff and landing: the leading and trailing runs of seconds whose altitude is
    below ``CRUISE_ALT_FRACTION`` x the track's median altitude (or NaN); ``(n,)`` bool."""
    alt = np.asarray(alt_m, dtype=np.float64)
    if len(alt) == 0 or not np.isfinite(alt).any():
        return np.zeros(len(alt), dtype=bool)
    with np.errstate(invalid="ignore"):
        low = ~(alt >= CRUISE_ALT_FRACTION * np.nanmedian(alt))
    leading = np.cumprod(low).astype(bool)
    trailing = np.cumprod(low[::-1])[::-1].astype(bool)
    return ~(leading | trailing)


def choose_target(
    site: SiteGeometry, xy: np.ndarray, speed_ms: np.ndarray, alt_m: np.ndarray
) -> Target:
    """Where the drone lingers (SPEC §9.2 as amended by D-046).

    ``xy`` (n, 2), ``speed_ms`` (n,) and ``alt_m`` (n,) are 1 Hz rows; NaN rows are ignored.
    Candidate seconds: in flight (``in_flight_mask``), with a finite speed, and within
    ``NEAR_FENCE_M`` of the fence (all in-flight seconds if fewer than ``MIN_NEAR_S``). Of those,
    the slowest 50% (speed at or below their median) vote: the target with the smallest median
    distance wins; ties go to the earlier target in ``site.targets``.
    """
    xy = np.asarray(xy, dtype=np.float64)
    speed = np.asarray(speed_ms, dtype=np.float64)
    pos = np.isfinite(xy).all(axis=1)
    if not pos.any():
        raise ValueError("cannot choose a target for a track with no positions")
    ok = pos & np.isfinite(speed) & in_flight_mask(alt_m)
    if not ok.any():
        ok = pos & np.isfinite(speed) if (pos & np.isfinite(speed)).any() else pos
    fence_d = np.full(len(xy), np.inf)
    fence_d[ok] = shapely.distance(shapely.points(xy[ok]), site.fence)
    near = ok & (fence_d <= NEAR_FENCE_M)
    if near.sum() >= MIN_NEAR_S:
        ok = near
    sel = ok & (speed <= np.median(speed[ok])) if np.isfinite(speed[ok]).all() else ok
    medians = [float(np.median(t.distance(xy[sel]))) for t in site.targets]
    return site.targets[int(np.argmin(medians))]


def add_target_columns(features: pd.DataFrame, target: Target) -> pd.DataFrame:
    """Add ``x_rel_m``, ``y_rel_m``, ``dist_target_m`` and ``bearing_rel_deg`` (from the target
    centroid to the drone) to 1 Hz features; returns a new frame."""
    xy = features[["x_m", "y_m"]].to_numpy(dtype=np.float64)
    rel = geo.region_to_target(xy, target.centroid)
    out = features.copy()
    out["x_rel_m"] = rel[:, 0]
    out["y_rel_m"] = rel[:, 1]
    out["dist_target_m"] = target.distance(xy)
    brg = geo.bearing(np.zeros(2), rel)
    brg[~np.isfinite(rel).all(axis=1)] = np.nan
    out["bearing_rel_deg"] = brg
    return out


def track_features(
    points: pd.DataFrame, site: SiteGeometry, scoring: ScoringConfig
) -> tuple[pd.DataFrame, Target]:
    """Points of one (possibly partial) track -> 1 Hz features with target columns, and the target.

    Uses only the points given, so a live track truncated at T never sees later points.
    """
    f = resample(points, scoring.features.max_interp_gap_s)
    if len(f) == 0:
        raise ValueError("track has no whole second to resample")
    target = choose_target(
        site, f[["x_m", "y_m"]].to_numpy(), f["speed_ms"].to_numpy(), f["alt_m"].to_numpy()
    )
    return add_target_columns(f, target), target


def channel_matrix(features: pd.DataFrame, scoring: ScoringConfig) -> np.ndarray:
    """The raw matching channels, ``(n, c)`` float64 in ``scoring.features.channels`` order."""
    return features[scoring.features.channels].to_numpy(dtype=np.float64)


def normalize(matrix: np.ndarray, weights: np.ndarray | list[float]) -> np.ndarray:
    """Z-normalize each column of ``matrix`` (n, c) over its finite values (σ floor 1e-3) and
    multiply by ``weights`` (c,). NaN stays NaN; an all-NaN column stays NaN."""
    m = np.asarray(matrix, dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mu = np.nanmean(m, axis=0)
        sd = np.nanstd(m, axis=0)
    sd = np.where(np.isfinite(sd), np.maximum(sd, SIGMA_FLOOR), SIGMA_FLOOR)
    return (m - mu) / sd * np.asarray(weights, dtype=np.float64)
