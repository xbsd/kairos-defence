"""Track signatures (SPEC §9.4): one row of summary fields per track.

Inputs are the track's 1 Hz features with target columns (``channels.track_features``), its raw
first and last radar points, and what the RF and Remote ID sensors said about it
(``SensorContext``, built by the DuckDB adapter from the §11.2 joins). All positions in the output
are target-relative meters.

Gap-fills (D-047): the loiter radius is the median distance from the target *centroid* over the
loiter seconds; ``loiter_dir`` sums bearing changes only over seconds outside the target polygon and
is ``ccw`` when the bearing from the target decreases (D-024); takeoff and landing are the leading
and trailing seconds below 0.8 x the median altitude.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from kairos_defense import geo
from kairos_defense.features.channels import SiteGeometry, Target, in_flight_mask

APPROACH_WITHIN_M = 1000.0
LOITER_SPEED_FACTOR = 1.2
LOITER_WITHIN_M = 600.0
LOITER_MIN_S = 10  # fewer loiter seconds than this: no loiter
COVERAGE_MIN_DEG = 180.0
DWELL_FACTOR = 1.5
SEEN_LOW_M = 30.0  # first/last point below this: takeoff/landing seen (D-003)
NIGHT_WRAP_HOUR = 12  # local times before noon belong to the previous night: 01:00 -> 1500

SIGNATURE_COLUMNS = [
    "track_id", "incident_id", "installation_id", "region_id", "start_ts", "end_ts", "duration_s",
    "target_asset_id", "target_kind", "approach_bearing_deg", "loiter_radius_m", "loiter_dir",
    "dwell_s", "alt_median_m", "tod_minutes", "launch_x_rel_m", "launch_y_rel_m",
    "recovery_x_rel_m", "recovery_y_rel_m", "rf_family", "rid_present", "rid_serial",
]  # fmt: skip


@dataclass(frozen=True)
class SensorContext:
    """RF and Remote ID evidence for one track (SPEC §9.4, §11.2; D-048).

    ``rf_family``: mode of associated RF detections, ``"unknown"`` if none. ``rid_serials``:
    serials heard within ±5 s and 100 m of the track, most frequent first. ``rid_operator_xy``:
    the main serial's median operator position (region meters), or None.
    """

    rf_family: str = "unknown"
    rid_serials: tuple[str, ...] = ()
    rid_operator_xy: tuple[float, float] | None = None

    @property
    def rid_stable(self) -> bool:
        """One serial for the whole track."""
        return len(self.rid_serials) == 1


def tod_minutes(start_utc: datetime, utc_offset_hours: int) -> int:
    """Local minutes after midnight at ``start_utc``; before noon wraps past midnight (01:00 ->
    1500), so a night's flights sort in order."""
    local = start_utc + timedelta(hours=utc_offset_hours)
    m = local.hour * 60 + local.minute
    return m + 1440 if local.hour < NIGHT_WRAP_HOUR else m


def approach_bearing(f: pd.DataFrame) -> float | None:
    """Bearing from the target centroid to the first second within 1,000 m of the target."""
    hit = np.flatnonzero(f["dist_target_m"].to_numpy() <= APPROACH_WITHIN_M)
    return None if len(hit) == 0 else float(f["bearing_rel_deg"].iloc[hit[0]])


def loiter_mask(f: pd.DataFrame) -> np.ndarray:
    """Seconds slower than 1.2 x the median speed and within 600 m of the target; ``(n,)`` bool."""
    speed = f["speed_ms"].to_numpy(dtype=np.float64)
    dist = f["dist_target_m"].to_numpy(dtype=np.float64)
    if not np.isfinite(speed).any():
        return np.zeros(len(f), dtype=bool)
    with np.errstate(invalid="ignore"):
        return (speed < LOITER_SPEED_FACTOR * np.nanmedian(speed)) & (dist <= LOITER_WITHIN_M)


def loiter_direction(f: pd.DataFrame, loiter: np.ndarray) -> str:
    """``cw``, ``ccw`` or ``none``: the sign of the net bearing change around the target over
    consecutive loiter seconds outside the target polygon; ``none`` below 180 deg net coverage.
    A decreasing bearing is counter-clockwise seen from above (D-024)."""
    keep = loiter & (f["dist_target_m"].to_numpy() > 0)
    brg = f["bearing_rel_deg"].to_numpy(dtype=np.float64)
    t = f["t_s"].to_numpy()
    pair = keep[1:] & keep[:-1] & (np.diff(t) == 1)
    swept = float(np.nansum(geo.wrap180(np.diff(brg))[pair])) if pair.any() else 0.0
    if abs(swept) < COVERAGE_MIN_DEG:
        return "none"
    return "ccw" if swept < 0 else "cw"


def _rel(xy, target: Target) -> tuple[float | None, float | None]:
    if xy is None:
        return None, None
    rel = geo.region_to_target(np.asarray(xy, dtype=np.float64), target.centroid)
    return float(rel[0]), float(rel[1])


def signature(
    f: pd.DataFrame,
    target: Target,
    first_point: pd.Series,
    last_point: pd.Series,
    site: SiteGeometry,
    ctx: SensorContext,
    ids: dict[str, str],
) -> dict:
    """One §7.2 ``track_signatures`` row (``SIGNATURE_COLUMNS``).

    ``f``: 1 Hz features with target columns. ``first_point``/``last_point``: raw radar points
    (``ts``, ``x_m``, ``y_m``, ``alt_m``). ``ids``: ``track_id`` and ``incident_id``.
    """
    loiter = loiter_mask(f)
    centroid_d = np.hypot(f["x_rel_m"].to_numpy(), f["y_rel_m"].to_numpy())
    radius = float(np.median(centroid_d[loiter])) if loiter.sum() >= LOITER_MIN_S else None
    direction = loiter_direction(f, loiter) if radius is not None else "none"
    dwell = 0.0
    if radius is not None:
        with np.errstate(invalid="ignore"):
            dwell = float(np.sum(f["dist_target_m"].to_numpy() <= DWELL_FACTOR * radius))
    alt = f["alt_m"].to_numpy(dtype=np.float64)
    flying = in_flight_mask(alt)
    alt_med = float(np.nanmedian(alt[flying] if flying.any() else alt))

    if ctx.rid_stable and ctx.rid_operator_xy is not None:
        launch = ctx.rid_operator_xy
    elif first_point["alt_m"] < SEEN_LOW_M:
        launch = (first_point["x_m"], first_point["y_m"])
    else:
        launch = None
    recovery = (last_point["x_m"], last_point["y_m"]) if last_point["alt_m"] < SEEN_LOW_M else None
    lx, ly = _rel(launch, target)
    rx, ry = _rel(recovery, target)

    start = pd.Timestamp(first_point["ts"]).to_pydatetime()
    end = pd.Timestamp(last_point["ts"]).to_pydatetime()
    return {
        "track_id": ids["track_id"],
        "incident_id": ids["incident_id"],
        "installation_id": site.installation_id,
        "region_id": site.region_id,
        "start_ts": start,
        "end_ts": end,
        "duration_s": (end - start).total_seconds(),
        "target_asset_id": target.asset_id,
        "target_kind": target.kind,
        "approach_bearing_deg": approach_bearing(f),
        "loiter_radius_m": radius,
        "loiter_dir": direction,
        "dwell_s": dwell,
        "alt_median_m": alt_med,
        "tod_minutes": tod_minutes(start, site.utc_offset_hours),
        "launch_x_rel_m": lx,
        "launch_y_rel_m": ly,
        "recovery_x_rel_m": rx,
        "recovery_y_rel_m": ry,
        "rf_family": ctx.rf_family,
        "rid_present": bool(ctx.rid_serials),
        "rid_serial": ctx.rid_serials[0] if ctx.rid_serials else None,
    }
