"""Swarm choreography matching (SPEC §14, D-149).

1. The query swarm is read from raw radar points up to the query second (``load_swarm``), so a live
   swarm never sees its future (rule 3).
2. Prefilter: the LanceDB ``swarm_windows`` table (one 96-d PAA vector per history swarm incident),
   pre-filtered to incidents that started before the query (``start_ts_ms < query start``).
   There are few swarms, so every pre-filtered incident is re-ranked.
3. Re-rank with ``dtw_ndim.distance`` on the z-normalized descriptor series (``swarm_series``).
   A query seen for n seconds is compared with candidate prefixes of m = n × pace seconds, pace in
   ``swarm.pace_range`` (the same team flies the same choreography faster or slower), each prefix
   z-normalized on its own, with a Sakoe-Chiba band of ``dtw.band_fraction`` of the longer
   series. The distance is the smallest ``d / sqrt(n + m)``; similarity is ``1 / (1 + distance)``.
4. The best prefix gives the warp ratio (m / n) and the DTW path (the full-matrix alignment,
   ``dtw_rerank.series_path``), which aligns every query second with a matched second for the
   Swarm view (formation snapshots and descriptor curves). ``dtw_rerank`` stays the only module
   that imports dtaidistance.

Ties break by start time, then incident id. No truth is read here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.features.resample import epoch_ms
from kairos_defense.features.swarm_features import (
    DESCRIPTOR_COLUMNS,
    SwarmFlight,
    load_swarm,
    swarm_series,
    swarm_vector,
)
from kairos_defense.match.dtw_rerank import require_c, series_distance, series_path
from kairos_defense.ports import TrackStore, VectorStore

SWARM_TABLE = "swarm_windows"
FEATURES_TABLE = "swarm_features"
MODEL_VERSION = "swarm-dtw-v1"
PACE_STEPS = 15  # prefix lengths tried across ``swarm.pace_range`` (D-149)
MIN_SECONDS = 20  # a query needs this many described seconds to be matched
PREFILTER_K = 200


class SwarmIndexMissing(RuntimeError):
    """``swarm_windows`` or ``swarm_features`` is missing: run ``make index``."""


@dataclass(frozen=True)
class SwarmMatch:
    rank: int
    incident_id: str
    installation_id: str
    region_id: str
    start_ts: pd.Timestamp
    n_drones: int
    duration_s: float
    distance: float
    similarity: float
    warp_ratio: float  # matched seconds per query second over the aligned prefix
    matched_s: int  # length of the aligned candidate prefix (s)

    def to_dict(self) -> dict:
        return {
            "rank": self.rank, "incident_id": self.incident_id,
            "installation_id": self.installation_id, "region_id": self.region_id,
            "start_ts": pd.Timestamp(self.start_ts).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_drones": self.n_drones, "duration_s": round(self.duration_s, 1),
            "distance": round(self.distance, 6), "similarity": round(self.similarity, 6),
            "warp_ratio": round(self.warp_ratio, 4), "matched_s": self.matched_s,
        }  # fmt: skip


@dataclass
class SwarmResult:
    query: SwarmFlight
    matches: list[SwarmMatch]
    paths: dict[str, list[tuple[int, int]]] = field(default_factory=dict)  # incident -> DTW path
    timings: dict[str, float] = field(default_factory=dict)

    def aligned(self, incident_id: str) -> list[int]:
        """For each described query second (row of ``query.descriptors``), the matched row of the
        candidate's descriptors: the last path pair for that query row."""
        path = self.paths.get(incident_id, [])
        n = len(self.query.descriptors)
        out = [0] * n
        for i, j in path:
            if 0 <= i < n:
                out[i] = int(j)
        return out


def dtw_band(n: int, m: int, fraction: float) -> int:
    """Sakoe-Chiba window for series of n and m samples: ``fraction`` of the longer, at least the
    length difference plus one (so a path always exists)."""
    return int(max(np.ceil(fraction * max(n, m)), abs(n - m) + 1, 2))


def prefix_lengths(n: int, m_max: int, pace_range: tuple[float, float] = (0.7, 1.4)) -> list[int]:
    """Candidate prefix lengths for a query of n seconds: n × pace over ``pace_range``, clipped to
    the candidate's length, unique and ascending."""
    paces = np.linspace(pace_range[0], pace_range[1], PACE_STEPS)
    lens = np.unique(np.clip(np.round(n * paces).astype(int), MIN_SECONDS, m_max))
    return [int(x) for x in lens if x >= 2]


def prefix_dtw(
    q: np.ndarray,
    cand_desc: pd.DataFrame,
    band_fraction: float,
    pace_range: tuple[float, float] = (0.7, 1.4),
) -> tuple[float, int]:
    """Smallest normalized DTW distance between the query series ``q`` (n, 6), already
    z-normalized, and the z-normalized prefixes of a candidate's descriptors. Returns
    ``(distance, prefix length)``; ``(inf, 0)`` when the candidate is too short."""
    n, m_max = len(q), len(cand_desc)
    best, best_m = np.inf, 0
    if n < 2 or m_max < 2:
        return best, best_m
    for m in prefix_lengths(n, m_max, pace_range):
        c = swarm_series(cand_desc.iloc[:m])
        d = series_distance(q, c, dtw_band(n, m, band_fraction)) / np.sqrt(n + m)
        if d < best - 1e-12:
            best, best_m = d, m
    return best, best_m


def warping_path(q: np.ndarray, c: np.ndarray) -> list[tuple[int, int]]:
    """The full-matrix DTW alignment of the query series to the matched prefix (Swarm view)."""
    return [(int(i), int(j)) for i, j in series_path(q, c)]


class SwarmMatcher:
    """§14 swarm search over the ports (``TrackStore`` for raw points and ``swarm_features``,
    ``VectorStore`` for ``swarm_windows``)."""

    model_version = MODEL_VERSION

    def __init__(self, store: TrackStore, vstore: VectorStore, scoring: ScoringConfig) -> None:
        require_c()  # D-013, D-064: the C extension is mandatory
        self.store, self.vstore, self.scoring = store, vstore, scoring
        self.pace_range = tuple(scoring.swarm.pace_range)
        self._desc: dict[str, pd.DataFrame] = {}

    def candidate_descriptors(self, incident_id: str) -> pd.DataFrame:
        """The indexed descriptors of one history swarm incident (``swarm_features``)."""
        if incident_id not in self._desc:
            cols = ", ".join(DESCRIPTOR_COLUMNS)
            df = self.store.sql(f"SELECT {cols} FROM {FEATURES_TABLE} WHERE incident_id = $i "
                                "ORDER BY t_s", {"i": incident_id})  # fmt: skip
            self._desc[incident_id] = df.reset_index(drop=True)
        return self._desc[incident_id]

    def candidates(self, query: SwarmFlight, vector: np.ndarray) -> pd.DataFrame:
        start_ms = epoch_ms(query.start_ts)
        where = f"start_ts_ms < {start_ms} AND incident_id != '{query.incident_id}'"
        try:
            return self.vstore.search(SWARM_TABLE, vector, where, PREFILTER_K)
        except (ValueError, FileNotFoundError, KeyError) as exc:  # table missing
            raise SwarmIndexMissing(f"{SWARM_TABLE} is missing: run `make index` ({exc})") from exc

    def match(self, incident_id: str, at_s: float | None = None, k: int = 5) -> SwarmResult:
        """Rank earlier history swarms against ``incident_id`` seen up to ``at_s`` seconds after
        its first radar point (None: its whole observed flight)."""
        t0 = time.perf_counter()
        query = load_swarm(self.store, incident_id, self.scoring, until_s=at_s)
        t1 = time.perf_counter()
        res = SwarmResult(query, [])
        if len(query.descriptors) < MIN_SECONDS:
            res.timings = {"load_ms": (t1 - t0) * 1000.0, "total_ms": (t1 - t0) * 1000.0}
            return res
        q = swarm_series(query.descriptors)
        cands = self.candidates(query, swarm_vector(q, self.scoring.windows.paa_segments))
        t2 = time.perf_counter()
        frac = self.scoring.dtw.band_fraction
        scored = []
        for row in cands.itertuples(index=False):
            desc = self.candidate_descriptors(row.incident_id)
            dist, m = prefix_dtw(q, desc, frac, self.pace_range)
            if not np.isfinite(dist):
                continue
            scored.append((dist, int(row.start_ts_ms), str(row.incident_id), m, row))
        scored.sort(key=lambda s: (s[0], s[1], s[2]))
        for rank, (dist, start_ms, inc, m, row) in enumerate(scored[:k], 1):
            res.matches.append(SwarmMatch(
                rank, inc, str(row.installation_id), str(row.region_id),
                pd.Timestamp(start_ms, unit="ms"), int(row.n_drones), float(row.duration_s),
                dist, 1.0 / (1.0 + dist), m / len(q), m))  # fmt: skip
            c = swarm_series(self.candidate_descriptors(inc).iloc[:m])
            res.paths[inc] = warping_path(q, c)
        t3 = time.perf_counter()
        res.timings = {"load_ms": (t1 - t0) * 1000.0, "prefilter_ms": (t2 - t1) * 1000.0,
                       "dtw_ms": (t3 - t2) * 1000.0, "total_ms": (t3 - t0) * 1000.0}  # fmt: skip
        return res
