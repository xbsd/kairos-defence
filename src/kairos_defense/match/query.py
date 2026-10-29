"""A query: a (possibly live) track as it looked T seconds after its first radar point.

Only points up to T are used: the target, the smoothing and the derivatives are all recomputed from
those points, so nothing after T can leak into the query (CLAUDE.md rule 3, SPEC §9.2 "recompute
every update"). T counts from the track's first radar point, which is also the query's start time
for the no-look-ahead filter (D-050).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import SiteGeometry, Target, load_site, track_features
from kairos_defense.features.resample import epoch_ms
from kairos_defense.features.windows import query_vector
from kairos_defense.ports import TrackStore


@dataclass(frozen=True)
class Query:
    track_id: str
    incident_id: str
    installation_id: str
    start_ts: datetime  # first radar point of the query track
    at_s: int  # seconds after the first point
    features: pd.DataFrame  # 1 Hz, from points up to at_s only
    target: Target
    vector: np.ndarray  # (80,) float32
    window_s: int  # W used for the search (§10.1)
    rows_used: int  # seconds in the query vector (< W before the smallest size, D-050)
    site: SiteGeometry | None = None  # the installation's geometry (for the partial signature)
    points: pd.DataFrame | None = None  # raw radar points up to at_s only

    @property
    def until(self) -> datetime:
        """The replay time: first radar point + T (nothing after it may be used)."""
        return self.start_ts + timedelta(seconds=self.at_s)

    @property
    def start_ms(self) -> int:
        return epoch_ms(self.start_ts)


def query_at(
    points: pd.DataFrame, site: SiteGeometry, at_s: int, scoring: ScoringConfig, ids: dict
) -> Query:
    """Build the query from a track's raw points as seen ``at_s`` seconds after its first point.

    ``ids`` holds ``track_id`` and ``incident_id``.
    """
    pts = points.sort_values("ts", kind="stable")
    first = pd.Timestamp(pts["ts"].iloc[0])
    seen = pts[pts["ts"] <= first + pd.Timedelta(seconds=at_s)]
    f, target = track_features(seen, site, scoring)
    vec, size, used = query_vector(f, scoring)
    return Query(ids["track_id"], ids["incident_id"], site.installation_id,
                 first.to_pydatetime(), int(at_s), f, target, vec, size, used, site,
                 seen.reset_index(drop=True))  # fmt: skip


def load_query(store: TrackStore, track_id: str, at_s: int, scoring: ScoringConfig) -> Query:
    """``query_at`` for a stored track (history or live), through the ``TrackStore`` port."""
    pts = store.track_points(track_id)
    if len(pts) == 0:
        raise KeyError(f"unknown track {track_id!r}")
    site = load_site(store, str(pts["installation_id"].iloc[0]))
    ids = {"track_id": track_id, "incident_id": str(pts["incident_id"].iloc[0])}
    return query_at(pts, site, at_s, scoring, ids)
