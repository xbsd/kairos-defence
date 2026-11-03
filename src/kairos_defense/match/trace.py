"""The matcher trace (D-187): a record of one ``DtwMatcher.match`` call, for the DTW workbench.

``TraceRecorder`` only reads what the matcher computed (the prefilter's rows, each candidate's
DTW distance and the time it took, the fusion features and scores, the final ranking) and adds
separate calls for what the matcher does not keep: the warping path of the first ``TRACE_PATHS``
candidates in the order computed (``dtw_rerank.alignment``: the matcher's own full-matrix
alignment with the segment's ends relaxed), down-sampled to at most ``MAX_POINTS`` points, their
curves on ``TRACE_CHANNEL`` and a ``THUMB`` × ``THUMB`` thumbnail of the accumulated cost matrix.
The time those extra calls take is ``trace_ms``: the overhead is measured, not guessed. With no
recorder the matcher runs exactly as before; with one its results are identical. Everything is
JSON-safe (no NaN, no infinity).
"""

from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.match import dtw_rerank
from kairos_defense.match.lens import paa

TRACE_PATHS = 50  # candidates with a path, curve and thumbnail: the ones the workbench replays
MAX_POINTS = 48
THUMB = 12
TRACE_CHANNEL = "dist_target_m"
TOP = 10


def _num(v: float | None, nd: int = 4) -> float | None:
    if v is None:
        return None
    v = float(v)
    return round(v, nd) if math.isfinite(v) else None


def downsample_path(path: np.ndarray, max_points: int = MAX_POINTS) -> list[list[int]]:
    """At most ``max_points`` pairs of ``path`` (p, 2), evenly spaced, first and last kept."""
    p = len(path)
    if p <= max_points:
        idx = np.arange(p)
    else:
        idx = np.unique(np.round(np.linspace(0, p - 1, max_points)).astype(int))
    return [[int(path[k, 0]), int(path[k, 1])] for k in idx]


def thumbnail(cost: np.ndarray, size: int = THUMB) -> list[list[float | None]]:
    """A ``size`` × ``size`` view of a cost matrix: the minimum of each block (None where every
    cell is unreachable). Rows are the query's samples, columns the candidate's."""
    n, m = cost.shape
    rows = np.linspace(0, n, size + 1).astype(int)
    cols = np.linspace(0, m, size + 1).astype(int)
    out = []
    for i in range(size):
        r0, r1 = rows[i], max(rows[i + 1], rows[i] + 1)
        line = []
        for j in range(size):
            c0, c1 = cols[j], max(cols[j + 1], cols[j] + 1)
            block = cost[min(r0, n - 1) : min(r1, n), min(c0, m - 1) : min(c1, m)]
            v = float(np.min(block)) if block.size else math.inf
            line.append(float(f"{v:.3g}") if math.isfinite(v) else None)  # 3 significant digits
        out.append(line)
    return out


def curve(values: np.ndarray, max_points: int = MAX_POINTS) -> list[float | None]:
    return [_num(v, 1) for v in paa(np.asarray(values, dtype=np.float64), max_points)]


class TraceRecorder:
    """Collects one match call's trace. ``paths``: how many candidates get a path (D-187).

    Columnar: the prefilter's columns hold one entry per candidate in prefilter order, which is
    also the order the DTW computes them and the fusion scores them, so the ``dtw`` and
    ``fusion`` columns line up with ``prefilter.track_id`` index by index."""

    def __init__(self, scoring: ScoringConfig, paths: int = TRACE_PATHS) -> None:
        self.scoring, self.paths = scoring, int(paths)
        self.channel = scoring.features.channels.index(TRACE_CHANNEL)
        self.extra_s = 0.0  # time spent on what only the trace needs
        self.doc: dict = {"version": 1, "trace_paths": self.paths, "channel": TRACE_CHANNEL}
        self.cols: dict[str, list] = {k: [] for k in ("distance", "d_norm", "band", "m", "ms_each")}
        self.detail: list[dict] = []

    # --- called by CandidateBuilder.build ------------------------------------------------------
    def query(self, q, live: np.ndarray) -> None:
        t0 = time.perf_counter()
        self.doc["query"] = {"track_id": q.track_id, "incident_id": q.incident_id,
                             "at_s": int(q.at_s), "window_s": int(q.window_s),
                             "rows_used": int(q.rows_used), "n": len(live),
                             "curve": curve(live[:, self.channel])}  # fmt: skip
        self.extra_s += time.perf_counter() - t0

    def prefilter(self, cands: pd.DataFrame, ms: float, k_windows: int) -> None:
        t0 = time.perf_counter()
        n = len(cands)
        col = (lambda k, f: [f(v) for v in cands[k]]) if n else (lambda k, f: [])
        self.doc["prefilter"] = {
            "ms": _num(ms, 3), "k_windows": int(k_windows), "candidates": n,
            "track_id": col("track_id", str), "incident_id": col("incident_id", str),
            "start_ts_ms": col("start_ts_ms", int),
            "distance": col("_distance", lambda v: _num(v, 6)),
            "window_s": col("window_s", int), "offset_s": col("offset_s", int),
        }  # fmt: skip
        self.extra_s += time.perf_counter() - t0

    def candidate(self, i: int, track_id: str, d_norm: float, n: int, m: int, ms: float,
                  live: np.ndarray, seg: np.ndarray) -> None:  # fmt: skip
        """One candidate's DTW, in the order computed; paths for the first ``paths``."""
        t0 = time.perf_counter()
        sc = self.scoring
        c = self.cols
        c["distance"].append(_num(d_norm * math.sqrt(n), 5))
        c["d_norm"].append(_num(d_norm, 6))
        c["band"].append(dtw_rerank.band_window(n, m, sc.dtw.band_fraction))
        c["m"].append(int(m))
        c["ms_each"].append(_num(ms, 4))
        if i < self.paths:
            self._detail(i, track_id, live, seg)
        self.extra_s += time.perf_counter() - t0

    def _detail(self, i: int, track_id: str, live: np.ndarray, seg: np.ndarray) -> None:
        sc = self.scoring
        path, cost = dtw_rerank.alignment(
            live, seg, sc.features.channel_weights, sc.dtw.normalize, sc.features.channel_scales
        )
        self.detail.append({"order": int(i), "track_id": track_id, "path": downsample_path(path),
                            "path_len": len(path), "curve": curve(seg[:, self.channel]),
                            "cost": thumbnail(cost)})  # fmt: skip

    def top_detail(self, order: int, track_id: str, live: np.ndarray, seg: np.ndarray) -> None:
        """A final top-10 track beyond the first ``paths``: its path too, so the fused top 5 is
        always shown aligned (kept in computed order)."""
        if any(d["order"] == order for d in self.detail):
            return
        t0 = time.perf_counter()
        self._detail(order, track_id, live, seg)
        self.detail.sort(key=lambda d: d["order"])
        self.extra_s += time.perf_counter() - t0

    def dtw(self, ms: float) -> None:
        sc = self.scoring
        q = self.doc.get("query", {})
        self.doc["dtw"] = {"ms": _num(ms, 3), "band_fraction": float(sc.dtw.band_fraction),
                           "normalize": sc.dtw.normalize, "n": q.get("n"), **self.cols,
                           "detail": self.detail}  # fmt: skip

    # --- called by DtwMatcher.match ---------------------------------------------------------------
    def fusion(self, rows: pd.DataFrame, X: np.ndarray, scores: np.ndarray, model, tau: float,
               ms: float) -> None:  # fmt: skip
        self.doc["dtw"]["shape_sim"] = [_num(v, 6) for v in rows["shape_sim"].to_numpy()]
        self.doc["fusion"] = {
            "ms": _num(ms, 3), "features": list(model.features), "tau": _num(tau, 6),
            "coefficients": [_num(c, 6) for c in model.coefficients],
            "intercept": _num(model.intercept, 6),
            "values": [[_num(v, 4) for v in x] for x in X],
            "score": [_num(v, 6) for v in scores],
        }  # fmt: skip

    def ranking(self, matches, explain_ms: float) -> None:
        self.doc["ranking"] = [{"rank": k, "track_id": m.track_id, "incident_id": m.incident_id,
                                "installation_id": m.installation_id,
                                "score": _num(m.score, 6), "shape_sim": _num(m.shape_sim, 6),
                                "reasons": list(m.reasons)}
                               for k, m in enumerate(matches[:TOP], 1)]  # fmt: skip
        self.doc["explain_ms"] = _num(explain_ms, 3)

    def finish(self, total_ms: float) -> dict:
        self.doc["total_ms"] = _num(total_ms, 3)
        self.doc["trace_ms"] = _num(self.extra_s * 1e3, 3)
        return self.doc
