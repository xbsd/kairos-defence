"""Candidate features for the DTW matcher (SPEC §10.1): everything before the fusion model.

``CandidateBuilder.build(q)`` runs the prefilter (§10.3), the query's partial signature (§10.5),
the anchored DTW of every candidate (§10.4) and the six context features. It needs no model, so
training (``kairos_defense.eval.training``) and serving (``matcher.DtwMatcher``) share it and
cannot drift (D-073). History features never change between index builds, so each builder keeps
the candidates' raw channels in memory.

``check_index`` refuses an index whose window vectors were built with another recipe (D-075).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import channel_matrix
from kairos_defense.features.windows import iter_windows
from kairos_defense.match import dtw_rerank
from kairos_defense.match.fusion import context_frame
from kairos_defense.match.live_signature import query_signature
from kairos_defense.match.prefilter import WINDOWS_TABLE, LookAheadError, prefilter
from kairos_defense.match.query import Query
from kairos_defense.ports import TrackStore, VectorStore

STALE_TOLERANCE = 1e-6  # squared L2 between a stored window and the same window rebuilt now
FAR_FUTURE = datetime(9999, 1, 1)


class IndexStale(RuntimeError):
    """The LanceDB windows were built with a different vector recipe (or not at all)."""


@dataclass
class Candidates:
    """One query's candidates in prefilter order: the prefilter columns plus ``d_norm`` and the
    ``CONTEXT`` features; ``signatures`` holds the candidates' stored signatures by track id."""

    query: Query
    rows: pd.DataFrame
    signature: dict  # the query's partial signature
    signatures: pd.DataFrame
    timings: dict[str, float] = field(default_factory=dict)


class CandidateBuilder:
    """Prefilter, partial signature, anchored DTW and context features for queries."""

    def __init__(self, store: TrackStore, vstore: VectorStore, scoring: ScoringConfig) -> None:
        self.store, self.vstore, self.scoring = store, vstore, scoring
        self._raw: dict[str, np.ndarray] = {}  # track_id -> (n, 5) raw channels, row = t_s

    def raw_channels(self, track_ids: list[str]) -> dict[str, np.ndarray]:
        """Raw channel matrices of history tracks (cached; row i is t_s = i)."""
        missing = sorted(set(track_ids) - self._raw.keys())
        if missing:
            f = self.store.features_many(missing)
            for tid, rows in f.groupby("track_id", sort=False):
                self._raw[str(tid)] = channel_matrix(rows, self.scoring)
        return {t: self._raw[t] for t in track_ids if t in self._raw}

    def build(self, q: Query) -> Candidates:
        sc = self.scoring
        t0 = time.perf_counter()
        cands = prefilter(q, self.vstore, sc)
        t1 = time.perf_counter()
        qsig = query_signature(self.store, q)
        sigs = self.store.tracks_before(q.start_ts, q.incident_id).set_index("track_id")
        t2 = time.perf_counter()
        ids = cands["track_id"].astype(str).tolist() if len(cands) else []
        absent = sorted(set(ids) - set(sigs.index))
        if absent:
            raise LookAheadError(f"{len(absent)} candidate(s) for {q.track_id} have no earlier "
                                 f"signature: {absent[:3]}")  # fmt: skip
        live = channel_matrix(q.features.iloc[-q.rows_used :], sc)
        raw = self.raw_channels(ids)
        w, band = sc.features.channel_weights, sc.dtw.band_fraction
        before, after = sc.dtw.anchor_before, sc.dtw.anchor_after
        d_norm = np.empty(len(ids))
        for i, (tid, off, size) in enumerate(
            zip(ids, cands.get("offset_s", []), cands.get("window_s", []), strict=True)
        ):
            series = raw[tid]
            lo, hi = dtw_rerank.anchor_bounds(int(off), int(size), len(series), before, after)
            d_norm[i] = dtw_rerank.shape_distance(live, series[lo:hi], w, band)
        t3 = time.perf_counter()
        csigs = sigs.loc[ids]
        ctx = context_frame(qsig, csigs).reset_index(drop=True)
        rows = pd.concat([cands.reset_index(drop=True), ctx], axis=1).assign(d_norm=d_norm)
        t4 = time.perf_counter()
        timings = {"prefilter_ms": (t1 - t0) * 1e3, "signature_ms": (t2 - t1) * 1e3,
                   "dtw_ms": (t3 - t2) * 1e3, "features_ms": (t4 - t3) * 1e3}  # fmt: skip
        return Candidates(q, rows, qsig, csigs, timings)

    def segment(self, track_id: str, offset_s: int, window_s: int) -> np.ndarray:
        """A candidate's anchored segment (raw channels), for the warp ratio."""
        series = self.raw_channels([track_id])[track_id]
        sc = self.scoring
        lo, hi = dtw_rerank.anchor_bounds(offset_s, window_s, len(series), sc.dtw.anchor_before,
                                          sc.dtw.anchor_after)  # fmt: skip
        return series[lo:hi]


def check_index(store: TrackStore, vstore: VectorStore, scoring: ScoringConfig) -> str:
    """Rebuild the first window of each size of the earliest indexed track with the current
    configuration and look each one up by id (k = 1); raise ``IndexStale`` unless every stored
    vector is within ``STALE_TOLERANCE`` (D-075). Returns the probe track id."""
    sigs = store.tracks_before(FAR_FUTURE)
    if len(sigs) == 0:
        raise IndexStale("no indexed track: run `make index`")
    probe = str(sigs["track_id"].iloc[0])
    feats = store.features_many([probe])
    first: dict[int, object] = {}
    for w in iter_windows(feats, scoring):
        first.setdefault(w.window_s, w)
    if not first:
        raise IndexStale(f"probe track {probe} has no window: run `make index`")
    for w in first.values():
        wid = f"{probe}:{w.window_s}:{w.offset_s}"
        hit = vstore.search(WINDOWS_TABLE, w.vector, f"window_id = '{wid}'", 1)
        if len(hit) == 0 or float(hit["_distance"].iloc[0]) > STALE_TOLERANCE:
            raise IndexStale(
                f"index is stale: run `make index` (window {wid} does not match the current "
                f"vector recipe, windows.normalize = {scoring.windows.normalize})"
            )
    return probe
