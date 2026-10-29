"""Forecast error and report linkage for the evaluation (SPEC §19.3, §13 step 8, D-088).

``Downstream`` runs after the ranker has been timed, so the §10.9 latency keys keep their
meaning; its own timings are reported apart (``latency_forecast_*``, ``latency_recall_*``).

- Forecast error at T: the distance from the §13 center to the track's true recovery point; a
  query with no forecast counts as an infinite error.
- Report linkage at T = 120 s: for each of the top 3 distinct matched incidents of the fused
  ranking, its *relevant* reports are those with at least one true clue (``clue_truth``) filed by
  the replay time; a relevant report is *retrieved* when it is in the recall top k for that match,
  with tonight's default query. Linkage = Σ retrieved / Σ relevant.

Truth is read here (``kairos_defense.eval``) and only used to label results.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from kairos_defense.config import Config
from kairos_defense.eval.truth import clue_truth
from kairos_defense.forecast.analog import Forecast, forecast
from kairos_defense.match.query import Query
from kairos_defense.ports import Embedder, ReportIndex, TrackStore, VectorStore
from kairos_defense.recall.embed import make_embedder
from kairos_defense.recall.search import RecallResult, ReportRecall

FORECAST_AT = (90, 120)
LINKAGE_AT = 120
LINKAGE_MATCHES = 3


def forecast_error(fc: Forecast | None, true_xy) -> float:
    """Meters from the forecast center to ``true_xy``; ``inf`` without a forecast."""
    if fc is None:
        return float("inf")
    x, y = (float(v) for v in true_xy)
    return float(np.hypot(fc.center_x_m - x, fc.center_y_m - y))


def linkage_counts(
    recall: RecallResult, relevant: dict[str, set[str]]
) -> tuple[int, int, dict[str, tuple[int, int]]]:
    """``(retrieved, relevant, per incident)`` for one query: ``relevant`` maps a matched
    incident to its true-clue report ids filed by the replay time."""
    per = {}
    for mr in recall.matches:
        want = relevant.get(mr.incident_id, set())
        got = {r.report_id for r in mr.reports} & want
        per[mr.incident_id] = (len(got), len(want))
    return sum(h for h, _ in per.values()), sum(n for _, n in per.values()), per


@dataclass
class Downstream:
    """Forecast and recall labelling for one evaluation run (built once)."""

    cfg: Config
    store: TrackStore
    vstore: VectorStore
    truth: pd.DataFrame  # eval.truth.track_truth
    reports: ReportIndex | None = None
    embedder: Embedder | None = None

    def __post_init__(self) -> None:
        self.recovery = self.truth.set_index("track_id")[["recovery_x_m", "recovery_y_m"]]
        self.recall = None
        if self.reports is not None:
            emb = self.embedder or make_embedder(self.cfg.app)
            self.recall = ReportRecall(self.store, self.reports, self.vstore, emb,
                                       self.cfg.scoring)  # fmt: skip
            ct = clue_truth(self.cfg.app)
            true_ids = set(ct.loc[ct["is_true"].astype(bool), "report_id"])
            rep = self.store.sql("SELECT report_id, incident_id, report_ts FROM reports")
            self.clue_reports = rep[rep["report_id"].isin(true_ids)]

    def relevant(self, incident_ids, until) -> dict[str, set[str]]:
        """True-clue reports of ``incident_ids`` filed by ``until``."""
        r = self.clue_reports
        r = r[r["incident_id"].isin(list(incident_ids)) & (r["report_ts"] <= pd.Timestamp(until))]
        return {i: set(g["report_id"]) for i, g in r.groupby("incident_id")}

    def forecast(self, q: Query, result) -> tuple[Forecast | None, float, float]:
        """``(forecast, error m, ms)`` for one query."""
        t0 = time.perf_counter()
        fc = forecast(self.store, q, result, self.cfg.scoring)
        ms = (time.perf_counter() - t0) * 1e3
        return fc, forecast_error(fc, self.recovery.loc[q.track_id]), ms

    def linkage(self, q: Query, result, zone_roads=()) -> tuple[int, int, float, RecallResult]:
        """``(retrieved, relevant, ms per match, recall)`` at the query's T (needs reports)."""
        if self.recall is None:
            raise RuntimeError("no report index: report linkage needs `make index`")
        rec = self.recall.for_matches(q, result, zone_roads, n=LINKAGE_MATCHES)
        hits, total, _ = linkage_counts(rec, self.relevant([m.incident_id for m in rec.matches],
                                                           q.until))  # fmt: skip
        per_match = rec.timings["total_ms"] / max(len(rec.matches), 1)
        return hits, total, per_match, rec

    def outcome_fields(self, q: Query, result) -> dict:
        """``Outcome`` fields for one ranked query: forecast at T = 90 and 120 s, linkage at
        120 s (when a report index is given)."""
        out: dict = {}
        if q.at_s in FORECAST_AT:
            fc, err, ms = self.forecast(q, result)
            out.update(forecast_error_m=err, forecast_ms=ms)
            if q.at_s == LINKAGE_AT and self.recall is not None:
                hits, total, rms, _ = self.linkage(q, result, fc.roads if fc else ())
                out.update(linkage_hits=hits, linkage_total=total, recall_ms=rms)
        return out
