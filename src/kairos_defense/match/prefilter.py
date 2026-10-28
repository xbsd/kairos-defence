"""Prefilter (SPEC §10.3): nearest PAA windows of tracks that started before the query.

``window_filter`` builds the LanceDB filter; the search itself goes through the ``VectorStore``
port (the LanceDB call lives in ``store/lance.py``, D-014). ``start_ts_ms < query start`` is
mandatory (CLAUDE.md rule 3); a returned row that breaks it raises ``LookAheadError``, so a store
that ignored the filter can never feed the matcher.
"""

from __future__ import annotations

import re

import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.match.query import Query
from kairos_defense.ports import VectorStore

WINDOWS_TABLE = "flight_windows"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")


class LookAheadError(RuntimeError):
    """A search result started at or after the query, or came from the query's own incident."""


def window_filter(window_s: int, start_ms: int, exclude_incident: str) -> str:
    """``window_s = W AND start_ts_ms < start AND incident_id != '<id>'`` (ids are validated)."""
    if not _SAFE_ID.match(exclude_incident):
        raise ValueError(f"unsafe incident id in a filter: {exclude_incident!r}")
    return (f"window_s = {int(window_s)} AND start_ts_ms < {int(start_ms)} "
            f"AND incident_id != '{exclude_incident}'")  # fmt: skip


def best_per_track(hits: pd.DataFrame, n: int) -> pd.DataFrame:
    """Each track's nearest window, then the ``n`` nearest tracks (ties by id: deterministic)."""
    if len(hits) == 0:
        return hits
    best = (
        hits.sort_values(["_distance", "window_id"], kind="stable")
        .groupby("track_id", as_index=False, sort=False)
        .first()
    )
    return best.sort_values(["_distance", "track_id"], kind="stable").head(n).reset_index(drop=True)


def prefilter(q: Query, store: VectorStore, scoring: ScoringConfig) -> pd.DataFrame:
    """Candidate tracks for ``q``: best window each, nearest first (``candidate_tracks`` max)."""
    flt = window_filter(q.window_s, q.start_ms, q.incident_id)
    hits = store.search(WINDOWS_TABLE, q.vector, flt, scoring.prefilter.k_windows)
    if len(hits):
        bad = (hits["start_ts_ms"] >= q.start_ms) | (hits["incident_id"] == q.incident_id)
        if bad.any():
            raise LookAheadError(
                f"{int(bad.sum())} result(s) for {q.track_id} are not strictly in its past"
            )
    return best_per_track(hits, scoring.prefilter.candidate_tracks)
