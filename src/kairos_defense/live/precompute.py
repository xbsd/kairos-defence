"""``kairos-defense replay --precompute`` (D-013, D-105): every rerun second and every feature
second of each live single-track incident, computed ahead into the result cache, so seeking and
Director at 5× never wait on the matcher.

The cache is keyed by a fingerprint of what the results depend on: the fusion model and DTW
calibration files, the scoring and embeddings configuration, the incident's points and the sizes
of the derived tables. A changed fingerprint makes the cache stale: it is cleared and recomputed.
The cached results are the ones the loop computes (same function, same inputs).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from kairos_defense.config import AppConfig, ScoringConfig
from kairos_defense.live.loop import CACHE_FORMAT, LiveLoop, result_name
from kairos_defense.match.fusion import CALIBRATION_FILE, MODEL_FILE
from kairos_defense.ports import TrackStore


def fingerprint(store: TrackStore, scoring: ScoringConfig, app: AppConfig,
                incident_id: str) -> str:  # fmt: skip
    """SHA-256 over everything a cached live result depends on (hex)."""
    h = hashlib.sha256(f"kairos-live-cache/{CACHE_FORMAT}\n".encode())
    for name in (MODEL_FILE, CALIBRATION_FILE):
        p = Path(app.paths.models) / name
        h.update(p.read_bytes() if p.exists() else b"missing")
    h.update(scoring.model_dump_json().encode())
    h.update(app.embeddings.model_dump_json().encode())
    counts = store.sql(
        "SELECT (SELECT count(*) FROM track_points WHERE incident_id = $i) AS points, "
        "(SELECT CAST(max(ts) AS VARCHAR) FROM track_points WHERE incident_id = $i) AS last_ts, "
        "(SELECT count(*) FROM track_signatures) AS signatures, "
        "(SELECT count(*) FROM track_features) AS features, "
        "(SELECT count(*) FROM reports) AS reports, "
        "(SELECT count(*) FROM report_clues) AS clues", {"i": incident_id},
    ).iloc[0].to_dict()  # fmt: skip
    h.update(json.dumps({k: str(v) for k, v in counts.items()}, sort_keys=True).encode())
    return h.hexdigest()


@dataclass(frozen=True)
class PrecomputeSummary:
    incident_id: str
    reruns: int
    computed: int
    cached: int
    features: int
    fingerprint: str
    elapsed_s: float


def precompute(loop: LiveLoop, *, force: bool = False) -> PrecomputeSummary:
    """Fill the cache for every rerun second (computing only what is missing, or everything with
    ``force``) and every feature second."""
    t0 = time.perf_counter()
    inc = loop.incident.incident_id
    computed = cached = 0
    for r in loop.schedule:
        hit = loop.cache.get(inc, result_name(r)) if loop.cache is not None else None
        if hit is not None and not force:
            cached += 1
            continue
        doc = loop.compute(r)
        if loop.cache is not None:
            loop.cache.put(inc, result_name(r), doc)
        computed += 1
    feats = loop.save_features()
    if loop.cache is not None:
        man = loop.cache.get(inc, "manifest") or {}
        loop.cache.put(inc, "manifest", {**man, "incident_id": inc, "format": CACHE_FORMAT,
                                         "fingerprint": loop.fingerprint,
                                         "reruns": loop.schedule, "features": feats,
                                         "complete": True})  # fmt: skip
    return PrecomputeSummary(inc, len(loop.schedule), computed, cached, feats,
                             loop.fingerprint or "", time.perf_counter() - t0)  # fmt: skip
