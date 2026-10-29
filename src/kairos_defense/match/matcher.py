"""The DTW matcher (SPEC §10.1, §10.8): prefilter → anchored DTW → logistic fusion → reasons.

``DtwMatcher.match(q)`` returns the fused ranking, the same candidates in prefilter order (the
§10.2 Euclidean baseline, so DTW lift is measured on the same run, D-076) and per-stage timings.
The warp ratio and the reasons are computed for the top ``EXPLAIN_TOP`` fused matches, the ones a
person reads; the rest keep ``warp_ratio`` NaN and no reasons (no invented numbers, D-054).
The matcher needs ``models/fusion_v1.json`` and ``models/dtw_calibration.json`` (``make models``);
it refuses a stale index (D-075) and a missing C extension (D-013).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import channel_matrix
from kairos_defense.match import dtw_rerank
from kairos_defense.match.baseline import _ts, rank_candidates
from kairos_defense.match.candidates import CandidateBuilder, check_index
from kairos_defense.match.explain import reasons
from kairos_defense.match.fusion import (
    CALIBRATION_FILE,
    MODEL_FILE,
    DtwCalibration,
    FusionModel,
    ModelError,
    feature_matrix,
)
from kairos_defense.match.query import Query
from kairos_defense.match.types import Match
from kairos_defense.ports import TrackStore, VectorStore

EXPLAIN_TOP = 20
EXTRA_FEATURES = ("d_norm", "euclidean_d2", "window_s")


@dataclass
class MatchResult:
    matches: list[Match]  # fused score, best first
    baseline: list[Match]  # the same candidates in prefilter (Euclidean) order
    timings: dict[str, float] = field(default_factory=dict)  # ms per stage and total
    # what the matcher already computed, for the forecast and recall (phase 5, D-087): the
    # query's partial signature and the candidates' stored signatures by track id (None: the
    # Euclidean baseline, whose callers read them through the ports)
    signature: dict | None = None
    signatures: pd.DataFrame | None = None


def load_models(models_dir: Path | str, scoring: ScoringConfig) -> tuple[FusionModel, float]:
    """The fusion model and τ (numeric ``scoring.dtw.tau`` overrides the calibration)."""
    d = Path(models_dir)
    model = FusionModel.load(d / MODEL_FILE, scoring.fusion.features)
    cal = DtwCalibration.load(d / CALIBRATION_FILE)
    if scoring.dtw.tau != "auto":
        return model, float(scoring.dtw.tau)
    if not np.isclose(cal.tau, model.tau, rtol=1e-12, atol=0.0):
        raise ModelError(f"fusion model and calibration disagree on τ: run `make models` "
                         f"({model.tau} against {cal.tau} in {d})")  # fmt: skip
    return model, cal.tau


class DtwMatcher:
    """DTW + fusion ranking of earlier tracks for a query (one per process: it caches)."""

    def __init__(
        self,
        store: TrackStore,
        vstore: VectorStore,
        scoring: ScoringConfig,
        models_dir: Path | str,
        *,
        verify_index: bool = True,
    ) -> None:
        dtw_rerank.require_c()
        self.scoring = scoring
        self.model, self.tau = load_models(models_dir, scoring)
        if verify_index:
            check_index(store, vstore, scoring)
        self.builder = CandidateBuilder(store, vstore, scoring)
        self._speed_col = scoring.features.channels.index("speed_ms")

    @property
    def model_version(self) -> str:
        return self.model.version

    def match(self, q: Query) -> MatchResult:
        t0 = time.perf_counter()
        c = self.builder.build(q)
        t1 = time.perf_counter()
        rows = c.rows.assign(shape_sim=dtw_rerank.shape_sim(c.rows["d_norm"].to_numpy(), self.tau))
        scores = self.model.predict(feature_matrix(rows, self.model.features))
        order = sorted(range(len(rows)), key=lambda i: (-scores[i], i))  # ties: prefilter order
        t2 = time.perf_counter()
        live = channel_matrix(q.features.iloc[-q.rows_used :], self.scoring)
        weights = self.scoring.features.channel_weights
        recs = rows.to_dict("records")
        out: list[Match] = []
        explain_s = 0.0
        for rank, i in enumerate(order):
            r = recs[i]
            feats = {f: float(r[f]) for f in self.model.features}
            feats.update({"d_norm": float(r["d_norm"]), "euclidean_d2": float(r["_distance"]),
                          "window_s": float(r["window_s"])})  # fmt: skip
            why: list[str] = []
            warp = float("nan")
            if rank < EXPLAIN_TOP:
                te = time.perf_counter()
                seg = self.builder.segment(str(r["track_id"]), int(r["offset_s"]),
                                           int(r["window_s"]))  # fmt: skip
                warp = dtw_rerank.warp_ratio(live, seg, weights, self._speed_col)
                csig = c.signatures.loc[str(r["track_id"])].to_dict()
                why = reasons(feats, self.model, warp, csig)
                explain_s += time.perf_counter() - te
            out.append(Match(
                query_incident_id=q.incident_id, track_id=str(r["track_id"]),
                incident_id=str(r["incident_id"]), installation_id=str(r["installation_id"]),
                start_ts=_ts(int(r["start_ts_ms"])), score=float(scores[i]),
                shape_sim=float(r["shape_sim"]), features=feats, reasons=why,
                warp_ratio=warp, window_offset_s=int(r["offset_s"]),
                model_version=self.model.version,
            ))  # fmt: skip
        t3 = time.perf_counter()
        timings = {**c.timings, "fusion_ms": (t2 - t1) * 1e3, "explain_ms": explain_s * 1e3,
                   "total_ms": (t3 - t0) * 1e3}  # fmt: skip
        return MatchResult(out, rank_candidates(q, c.rows), timings, c.signature, c.signatures)
