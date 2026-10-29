"""Analog forecast of the recovery zone (SPEC §13, D-087, D-090).

1. Walk the fused ranking; keep the first ``forecast.top_k`` matches whose stored signature has a
   known recovery point (§9.4: last radar point below 30 m) and that had ended by the replay time.
2. j*: the matched segment's row paired with tonight's last row on the DTW warping path
   (``dtw_rerank.warp_path`` with the shape distance's scaling, ``dtw.normalize``, and relaxed
   ends); ``lo + j*`` on the track.
3. Remainder: the matched track's target-relative positions after j* (gap rows dropped), ending
   at its recovery point.
4. Tonight's frame: anchor + relative vector, rotated clockwise by the approach-bearing difference
   when it exceeds 30°. The anchor is tonight's target centroid (``forecast.anchor: target``); with
   ``match_kind`` and tonight still reading the fence, the analog's own asset kind at tonight's
   base (D-090).
5. Center: score-weighted mean of the mapped recovery points; radius: max(``min_radius_m``,
   ``radius_factor`` × weighted RMS distance to the center).
6. Exit path: the top analog's mapped remainder, resampled to 60 points by arc length.
7. Roads of tonight's region crossing the zone (``LineString.intersects(circle)``).

Pure helpers take numpy arrays (region or target-relative meters, ``(n, 2)``); ``forecast`` reads
through the ports only. It never reads truth: the error against the true recovery point is
computed in ``kairos_defense.eval``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from shapely import wkt
from shapely.geometry import LineString, Point

from kairos_defense import geo
from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import SiteGeometry, Target, channel_matrix
from kairos_defense.match import dtw_rerank
from kairos_defense.match.live_signature import query_signature
from kairos_defense.match.query import Query
from kairos_defense.ports import TrackStore

PATH_POINTS = 60
ROTATE_ABOVE_DEG = 30.0


def _known(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def combine(
    points: np.ndarray, weights: np.ndarray, min_radius: float, factor: float
) -> tuple[np.ndarray, float]:
    """Step 5: weighted center ``(2,)`` and radius (m) of mapped recovery points ``(n, 2)``.
    Non-positive total weight falls back to equal weights."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    w = np.asarray(weights, dtype=np.float64).reshape(-1)
    if not np.isfinite(w).all() or w.sum() <= 0:
        w = np.ones(len(p))
    w = w / w.sum()
    center = (w[:, None] * p).sum(axis=0)
    rms = float(np.sqrt((w * ((p - center) ** 2).sum(axis=1)).sum()))
    return center, max(float(min_radius), float(factor) * rms)


def rotate_rel(xy: np.ndarray, deg: float) -> np.ndarray:
    """Rotate target-relative vectors clockwise by ``deg`` (adds ``deg`` to their bearings)."""
    return geo.rotate(np.asarray(xy, dtype=np.float64), float(deg))


def rotation_for(tonight_deg: float | None, match_deg: float | None) -> float:
    """Step 4: the clockwise turn from the match's approach to tonight's, when the two differ by
    more than 30°; 0 when either is unknown or they are within 30°."""
    if not (_known(tonight_deg) and _known(match_deg)):
        return 0.0
    d = float(geo.wrap180(float(tonight_deg) - float(match_deg)))
    return d if abs(d) > ROTATE_ABOVE_DEG else 0.0


def aligned_index(
    live: np.ndarray, seg: np.ndarray, weights, mode: str = "fixed", scales=None
) -> int:
    """Step 2: the segment row paired with the last live row on the warping path (raw channels
    ``(n, c)`` and ``(m, c)``), scaled like the shape distance (``dtw.normalize``, D-079, D-087);
    the segment's last row when either has under two rows."""
    if len(live) < 2 or len(seg) < 2:
        return max(len(seg) - 1, 0)
    path = dtw_rerank.warp_path(live, seg, weights, mode, scales)
    last = path[path[:, 0] == len(live) - 1]
    return int(last[:, 1].max())


def remainder(features: pd.DataFrame, j: int, recovery_rel) -> np.ndarray:
    """Step 3: target-relative positions ``(n, 2)`` after row ``t_s = j`` (gap and NaN rows
    dropped), ending at ``recovery_rel``."""
    f = features[features["t_s"] > j]
    ok = ~f["in_gap"].astype(bool) & f["x_rel_m"].notna() & f["y_rel_m"].notna()
    xy = f.loc[ok, ["x_rel_m", "y_rel_m"]].to_numpy(dtype=np.float64)
    return np.vstack([xy, np.asarray(recovery_rel, dtype=np.float64).reshape(1, 2)])


def resample_path(xy: np.ndarray, n: int = PATH_POINTS) -> np.ndarray:
    """Step 6: ``n`` points evenly spaced by arc length along ``xy`` ``(m, 2)``; ``(n, 2)``. A
    path of one point (or zero length) repeats its first point."""
    p = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
    if len(p) == 0:
        raise ValueError("cannot resample an empty path")
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
    if s[-1] <= 0:
        return np.repeat(p[:1], n, axis=0)
    u = np.linspace(0.0, s[-1], n)
    return np.column_stack([np.interp(u, s, p[:, 0]), np.interp(u, s, p[:, 1])])


def anchor_target(target: Target, site: SiteGeometry, analog_kind, mode: str) -> Target:
    """Step 4's anchor: tonight's target, or (``match_kind``, tonight still on the fence) the
    asset of the analog's kind at tonight's base when it has one (D-090)."""
    if mode == "match_kind" and target.kind == "fence" and analog_kind not in (None, "fence"):
        for t in site.targets:
            if t.kind == analog_kind:
                return t
    return target


def roads_crossing(center: np.ndarray, radius: float, lines: Mapping[str, LineString]) -> list:
    """Step 7: names of roads whose line intersects the zone circle, sorted."""
    zone = Point(float(center[0]), float(center[1])).buffer(float(radius), quad_segs=64)
    return sorted(name for name, line in lines.items() if line.intersects(zone))


@dataclass(frozen=True)
class Analog:
    incident_id: str
    track_id: str
    score: float
    target_kind: str
    recovery_rel_m: tuple[float, float]  # the match's own recovery, relative to its target
    rotation_deg: float
    anchor_asset_id: str
    aligned_t_s: int  # j* on the matched track (seconds after its first point)
    recovery_x_m: float  # mapped into tonight's region frame
    recovery_y_m: float
    remainder_points: int


@dataclass(frozen=True)
class Forecast:
    at_s: int
    target_asset_id: str
    anchor: str  # forecast.anchor mode
    center_x_m: float
    center_y_m: float
    radius_m: float
    path: np.ndarray  # (60, 2) region meters, the top analog's mapped remainder
    roads: tuple[str, ...]
    analogs: tuple[Analog, ...]

    def to_dict(self) -> dict:
        """The §16.3 ``forecast`` message fields plus the analogs (JSON-safe)."""
        return {"at_s": self.at_s, "target_asset_id": self.target_asset_id,
                "anchor": self.anchor, "center_x_m": self.center_x_m,
                "center_y_m": self.center_y_m, "radius_m": self.radius_m,
                "path": [[float(x), float(y)] for x, y in self.path], "roads": list(self.roads),
                "analogs": [asdict(a) | {"recovery_rel_m": list(a.recovery_rel_m)}
                            for a in self.analogs]}  # fmt: skip


def road_lines(store: TrackStore, region_id: str) -> dict[str, LineString]:
    """Road name -> line (region meters) for one region."""
    rows = store.sql("SELECT name, line_wkt FROM roads WHERE region_id = $r ORDER BY name",
                     {"r": region_id})  # fmt: skip
    return {str(r.name): wkt.loads(r.line_wkt) for r in rows.itertuples()}


def _signature(store: TrackStore, sigs: pd.DataFrame | None, track_id: str) -> dict:
    if sigs is not None and track_id in sigs.index:
        return sigs.loc[track_id].to_dict() | {"track_id": track_id}
    return store.signature(track_id)


def forecast(store: TrackStore, q: Query, result, scoring: ScoringConfig) -> Forecast | None:
    """§13 for query ``q`` and its ``MatchResult``; None when no match has a known recovery."""
    fc, sc = scoring.forecast, scoring
    if q.site is None:
        raise ValueError(f"query {q.track_id} carries no site (build it with query_at)")
    qsig = result.signature if result.signature is not None else query_signature(store, q)
    picked: list[tuple[object, dict]] = []
    for m in result.matches:
        msig = _signature(store, result.signatures, m.track_id)
        ended = pd.Timestamp(msig["end_ts"]) <= pd.Timestamp(q.until)
        if ended and _known(msig.get("recovery_x_rel_m")) and _known(msig.get("recovery_y_rel_m")):
            picked.append((m, msig))
        if len(picked) == fc.top_k:
            break
    if not picked:
        return None
    live = channel_matrix(q.features.iloc[-q.rows_used :], sc)
    weights = sc.features.channel_weights
    tonight_brg = qsig.get("approach_bearing_deg")
    analogs, mapped_rec, paths = [], [], []
    for m, msig in picked:
        f = store.features(m.track_id)
        raw = channel_matrix(f, sc)
        lo, hi = dtw_rerank.anchor_bounds(m.window_offset_s, int(m.features["window_s"]), len(raw),
                                          sc.dtw.anchor_before, sc.dtw.anchor_after)  # fmt: skip
        j = lo + aligned_index(live, raw[lo:hi], weights, sc.dtw.normalize,
                               sc.features.channel_scales)  # fmt: skip
        rec = (float(msig["recovery_x_rel_m"]), float(msig["recovery_y_rel_m"]))
        rot = rotation_for(tonight_brg, msig.get("approach_bearing_deg"))
        anchor = anchor_target(q.target, q.site, msig.get("target_kind"), fc.anchor)
        rem = anchor.centroid + rotate_rel(remainder(f, j, rec), rot)
        mapped_rec.append(rem[-1])
        paths.append(rem)
        analogs.append(Analog(m.incident_id, m.track_id, float(m.score),
                              str(msig.get("target_kind")), rec, rot, anchor.asset_id, int(j),
                              float(rem[-1][0]), float(rem[-1][1]), len(rem)))  # fmt: skip
    center, radius = combine(np.vstack(mapped_rec), np.array([a.score for a in analogs]),
                             fc.min_radius_m, fc.radius_factor)  # fmt: skip
    roads = roads_crossing(center, radius, road_lines(store, q.site.region_id))
    return Forecast(int(q.at_s), q.target.asset_id, fc.anchor, float(center[0]),
                    float(center[1]), radius, resample_path(paths[0]), tuple(roads),
                    tuple(analogs))  # fmt: skip
