"""History plus learned live history behind the same ports (D-172, D-176).

Live mode's matcher, forecast and recall read through ``CompositeTrackStore`` and
``CompositeVectorStore``: the read-only main database and LanceDB (the 18-month history) plus the
live-mode feed store and its own LanceDB folder (closed live incidents, learned). A track belongs
to the live side when its id starts with ``LIVE-`` (the app's own live ids, D-174); everything
else is history. Writes (``upsert``) go to the live side only, so the history is never changed.
The no-look-ahead filters stay where they are: in the queries the callers pass (rule 3).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np
import pandas as pd

from kairos_defense.ports import TrackStore

LIVE_PREFIX = "LIVE-"


def is_live_id(track_or_incident_id: str) -> bool:
    return str(track_or_incident_id).startswith(LIVE_PREFIX)


class CompositeTrackStore:
    """``TrackStore`` over ``main`` (history) and ``live`` (learned live tracks and the feed)."""

    def __init__(self, main: TrackStore, live: TrackStore) -> None:
        self.main, self.live = main, live

    def _owner(self, track_id: str) -> TrackStore:
        return self.live if is_live_id(track_id) else self.main

    def track_points(self, track_id: str) -> pd.DataFrame:
        return self._owner(track_id).track_points(track_id)

    def features(self, track_id: str) -> pd.DataFrame:
        return self._owner(track_id).features(track_id)

    def features_many(self, track_ids: Sequence[str]) -> pd.DataFrame:
        ids = [str(t) for t in track_ids]
        live = [t for t in ids if is_live_id(t)]
        hist = [t for t in ids if not is_live_id(t)]
        parts = [s.features_many(x) for s, x in ((self.main, hist), (self.live, live)) if x]
        if not parts:
            return self.main.features_many([])
        out = pd.concat([p for p in parts if len(p)] or parts[:1], ignore_index=True)
        return out.sort_values(["track_id", "t_s"], kind="stable").reset_index(drop=True)

    def sensor_context_until(self, track_id: str, until: datetime) -> dict:
        return self._owner(track_id).sensor_context_until(track_id, until)

    def signature(self, track_id: str) -> dict:
        return self._owner(track_id).signature(track_id)

    def tracks_before(self, ts: datetime, exclude_incident: str | None = None) -> pd.DataFrame:
        """§11.3 on both sides: signatures of tracks that started strictly before ``ts``."""
        a = self.main.tracks_before(ts, exclude_incident)
        b = self.live.tracks_before(ts, exclude_incident)
        if len(b) == 0:
            return a
        out = pd.concat([a, b], ignore_index=True) if len(a) else b
        return out.sort_values(["start_ts", "track_id"], kind="stable").reset_index(drop=True)

    def context_asof(self, track_id: str) -> pd.DataFrame:
        if is_live_id(track_id):  # no weather or base events for the live calendar (D-177)
            return pd.DataFrame(columns=["track_id", "t_s", "ts", "speed_ms", "weather_ts",
                                         "wind_ms", "wind_dir_deg", "visibility_km",
                                         "base_events"])  # fmt: skip
        return self.main.context_asof(track_id)

    def sql(self, query: str, params: dict | None = None) -> pd.DataFrame:
        """Site geometry, roads, reports and the rest: the history database."""
        return self.main.sql(query, params)


class CompositeVectorStore:
    """``VectorStore`` over the history's LanceDB and the live-mode LanceDB folder."""

    def __init__(self, main, live) -> None:
        self.main, self.live = main, live

    def has(self, table: str) -> bool:
        return self.main.has(table) or self.live.has(table)

    def upsert(self, table: str, rows: Sequence[dict]) -> None:
        self.live.upsert(table, rows)

    def search(self, table: str, vector: np.ndarray, where: str | None, k: int) -> pd.DataFrame:
        """The ``k`` nearest rows of both sides (same filter), merged by ``_distance``."""
        a = self.main.search(table, vector, where, k)
        if not self.live.has(table):
            return a
        b = self.live.search(table, vector, where, k)
        if len(b) == 0:
            return a
        out = pd.concat([a, b], ignore_index=True) if len(a) else b
        return out.sort_values("_distance", kind="stable").head(k).reset_index(drop=True)
