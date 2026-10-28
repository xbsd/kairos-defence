"""Euclidean baseline (SPEC §10.2): rank candidates by their best window distance alone.

This is the reference for "DTW lift" (§19) and stays runnable as ``match --method euclidean``.
Vectors are unit length and ``_distance`` is squared L2 in [0, 4], so ``score = 1 - d / 4`` is the
cosine similarity mapped to [0, 1] (D-054).
"""

from __future__ import annotations

from datetime import UTC, datetime

from kairos_defense.config import ScoringConfig
from kairos_defense.match.prefilter import prefilter
from kairos_defense.match.query import Query
from kairos_defense.match.types import Match
from kairos_defense.ports import VectorStore

MODEL_VERSION = "euclidean-v1"


def _ts(ms: int) -> datetime:
    """Epoch ms -> naive UTC datetime (the DuckDB convention)."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).replace(tzinfo=None)


def rank_candidates(q: Query, candidates) -> list[Match]:
    """Matches from prefilter candidates (already nearest first)."""
    out = []
    for c in candidates.to_dict("records"):
        d2 = float(c["_distance"])
        score = max(0.0, min(1.0, 1.0 - d2 / 4.0))
        out.append(
            Match(
                query_incident_id=q.incident_id,
                track_id=c["track_id"],
                incident_id=c["incident_id"],
                installation_id=c["installation_id"],
                start_ts=_ts(int(c["start_ts_ms"])),
                score=score,
                shape_sim=score,
                features={"euclidean_d2": d2, "window_s": float(c["window_s"])},
                window_offset_s=int(c["offset_s"]),
                model_version=MODEL_VERSION,
            )
        )
    return out


def euclidean_matches(q: Query, store: VectorStore, scoring: ScoringConfig) -> list[Match]:
    """Past tracks most like ``q``'s latest window, best first (at most ``candidate_tracks``)."""
    return rank_candidates(q, prefilter(q, store, scoring))
