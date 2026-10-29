"""Fusion training (SPEC §10.6): pairs from history only, labelled with truth, a logistic fit, τ.

This is the only place truth labels training pairs (CLAUDE.md rule 2): the matcher receives plain
JSON files. Queries are prober and copycat tracks on the training nights (months 1 to 12 by
default), each run as if live at every T in the split's grid. §10.6 also lists swarm drones; they
stay as candidates (negatives) but are not queries, because one drone's approach and launch in a
formation are not traits of its team and taught the model to ignore the approach bearing (D-078).
Candidates are exactly what the matcher's own ``CandidateBuilder`` returns (same prefilter,
``start < q.start``, own incident excluded), so training and serving cannot drift. Label 1 when the
candidate has the query's actor; hobbyists, other probers and copycats are the negatives.

τ is the median ``d_norm`` of the positive pairs; the model is
``LogisticRegression(class_weight="balanced")`` fitted on rows sorted by (query, T, candidate), so
the fit and the training hash are deterministic. Validation repeats the build on months 13 to 18
and is reported only, never used to choose a setting (D-070, D-073).
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score

from kairos_defense.config import Config
from kairos_defense.eval.harness import QueryCase, labelled_tracks, query_cases, track_list
from kairos_defense.match import dtw_rerank
from kairos_defense.match.candidates import CandidateBuilder, check_index
from kairos_defense.match.fusion import (
    CALIBRATION_FILE,
    CONTEXT,
    MODEL_FILE,
    DtwCalibration,
    FusionModel,
)
from kairos_defense.match.query import load_query
from kairos_defense.ports import TrackStore, VectorStore

log = logging.getLogger(__name__)

VERSION = "fusion-v1"
QUERY_KINDS = ("prober", "copycat")  # swarm drones are candidates only (D-078)


@dataclass(frozen=True)
class TrainSplit:
    """Training and validation nights (local, inclusive) and the T grid (s) of the queries."""

    train_first: date = date(2025, 3, 1)
    train_last: date = date(2026, 2, 28)  # months 1-12 (§10.6)
    valid_first: date = date(2026, 3, 1)
    valid_last: date = date(2026, 8, 31)  # months 13-18
    t_grid: tuple[int, ...] = (45, 60, 90, 120, 180)

    def to_json(self) -> dict:
        d = asdict(self)
        return {k: (v.isoformat() if isinstance(v, date) else list(v)) for k, v in d.items()}


@dataclass
class Pairs:
    """One row per (query track, T, candidate): ``keys`` (``query``, ``actor_type``, ``at_s``,
    ``track_id``, ``answerable``), ``context`` ``(n, 6)`` in ``CONTEXT`` order, ``d_norm``
    ``(n,)`` and the label ``y`` ``(n,)`` int8."""

    keys: pd.DataFrame
    context: np.ndarray
    d_norm: np.ndarray
    y: np.ndarray
    queries: int = 0

    def sort(self) -> Pairs:
        order = np.lexsort((self.keys["track_id"].to_numpy(), self.keys["at_s"].to_numpy(),
                            self.keys["query"].to_numpy()))  # fmt: skip
        return Pairs(self.keys.iloc[order].reset_index(drop=True), self.context[order],
                     self.d_norm[order], self.y[order], self.queries)  # fmt: skip

    def X(self, tau: float, order: list[str] | tuple[str, ...]) -> np.ndarray:
        """``(n, len(order))`` features with ``shape_sim = exp(−d_norm / τ)``."""
        cols = {"shape_sim": dtw_rerank.shape_sim(self.d_norm, tau)}
        cols.update({f: self.context[:, i] for i, f in enumerate(CONTEXT)})
        return np.column_stack([cols[f] for f in order]) if len(self.y) else np.zeros((0, 0))

    def hash(self) -> str:
        """SHA-256 over the pair keys, the features and the labels (deterministic)."""
        h = hashlib.sha256()
        h.update("\n".join(f"{q}|{t}|{c}" for q, t, c in zip(self.keys["query"], self.keys["at_s"],
                 self.keys["track_id"], strict=True)).encode())  # fmt: skip
        for a in (self.context, self.d_norm, self.y):
            h.update(np.ascontiguousarray(a).tobytes())
        return h.hexdigest()


def training_queries(
    store: TrackStore, truth: pd.DataFrame, first: date, last: date
) -> list[QueryCase]:
    """Prober and copycat history tracks on nights ``first``..``last`` (``QUERY_KINDS``)."""
    return query_cases(labelled_tracks(track_list(store), truth), QUERY_KINDS, first, last)


def build_pairs(
    builder: CandidateBuilder,
    queries: list[QueryCase],
    truth: pd.DataFrame,
    t_grid: tuple[int, ...],
) -> Pairs:
    """Run every query at every T through the matcher's candidate builder and label the pairs."""
    actor = truth.set_index("track_id")["actor_id"]
    keys, ctx, dn, ys = [], [], [], []
    for case in queries:
        for at in t_grid:
            q = load_query(builder.store, case.track_id, at, builder.scoring)
            rows = builder.build(q).rows
            if len(rows) == 0:
                continue
            ids = rows["track_id"].astype(str)
            keys.append(pd.DataFrame({"query": case.track_id, "actor_type": case.actor_type,
                                      "at_s": at, "track_id": ids.to_numpy(),
                                      "answerable": case.answerable}))  # fmt: skip
            ctx.append(rows[list(CONTEXT)].to_numpy(np.float64))
            dn.append(rows["d_norm"].to_numpy(np.float64))
            ys.append((actor.loc[ids].to_numpy() == case.actor_id).astype(np.int8))
    if not keys:
        empty = pd.DataFrame(columns=["query", "actor_type", "at_s", "track_id", "answerable"])
        return Pairs(empty, np.zeros((0, len(CONTEXT))), np.zeros(0), np.zeros(0, np.int8),
                     len(queries))  # fmt: skip
    return Pairs(pd.concat(keys, ignore_index=True), np.vstack(ctx), np.concatenate(dn),
                 np.concatenate(ys), len(queries)).sort()  # fmt: skip


def calibrate_tau(pairs: Pairs) -> float:
    """τ = median ``d_norm`` of the same-actor pairs (§10.4 step 4)."""
    pos = pairs.d_norm[pairs.y == 1]
    if len(pos) == 0:
        raise ValueError("no same-actor pair to calibrate τ on: widen the training split")
    return float(np.median(pos))


def fit(pairs: Pairs, tau: float, order: list[str] | tuple[str, ...]) -> tuple[list[float], float]:
    """Balanced logistic regression (§10.6): ``(coefficients in order, intercept)``."""
    if len(np.unique(pairs.y)) < 2:
        raise ValueError("training pairs need both labels")
    lr = LogisticRegression(class_weight="balanced", solver="lbfgs", max_iter=1000, C=1.0)
    lr.fit(pairs.X(tau, order), pairs.y)
    return [float(c) for c in lr.coef_[0]], float(lr.intercept_[0])


def _quantiles(x: np.ndarray) -> dict:
    if len(x) == 0:
        return {"p10": None, "p50": None, "p90": None}
    p10, p50, p90 = np.percentile(x, [10, 50, 90])
    return {"p10": round(float(p10), 6), "p50": round(float(p50), 6), "p90": round(float(p90), 6)}


def recall_at(scores: np.ndarray, pairs: Pairs, k: int = 5, at_s: int = 120) -> float | None:
    """Share of answerable prober queries at ``at_s`` whose top ``k`` by ``scores`` holds a
    same-actor candidate (a query with no candidates counts as a miss upstream: it has no rows)."""
    keys = pairs.keys.assign(score=scores, y=pairs.y)
    sel = keys[(keys.at_s == at_s) & (keys.actor_type == "prober") & keys.answerable]
    if len(sel) == 0:
        return None
    hits = [
        bool(g.sort_values("score", ascending=False, kind="stable").head(k)["y"].any())
        for _, g in sel.groupby("query", sort=True)
    ]
    return sum(hits) / len(hits)


def validate(model: FusionModel, pairs: Pairs) -> dict:
    """Pair counts, ROC AUC, log loss and prober Recall@5 at T = 120 s (report only)."""
    out: dict = {"queries": pairs.queries, "pairs": len(pairs.y), "positives": int(pairs.y.sum())}
    if len(pairs.y) == 0:
        return out
    p = model.predict(pairs.X(model.tau, model.features))
    if len(np.unique(pairs.y)) == 2:
        out["roc_auc"] = round(float(roc_auc_score(pairs.y, p)), 6)
        out["log_loss"] = round(float(log_loss(pairs.y, p, labels=[0, 1])), 6)
    r5 = recall_at(p, pairs)
    out["recall_at_5_t120_probers"] = None if r5 is None else round(r5, 6)
    return out


@dataclass
class TrainSummary:
    model: FusionModel
    calibration: DtwCalibration
    train: dict = field(default_factory=dict)  # queries, pairs, positives
    paths: list[Path] = field(default_factory=list)
    elapsed_s: float = 0.0


def train_models(
    cfg: Config,
    store: TrackStore,
    vstore: VectorStore,
    truth: pd.DataFrame,
    split: TrainSplit | None = None,
    models_dir: Path | str | None = None,
) -> TrainSummary:
    """Build the pairs, calibrate τ, fit, validate and write ``models/fusion_v1.json`` and
    ``models/dtw_calibration.json``. Only ``created_at`` differs between two runs."""
    t0 = time.perf_counter()
    split = split or TrainSplit()
    sc = cfg.scoring
    check_index(store, vstore, sc)
    builder = CandidateBuilder(store, vstore, sc)
    tq = training_queries(store, truth, split.train_first, split.train_last)
    train = build_pairs(builder, tq, truth, split.t_grid)
    log.info("training pairs: %d from %d queries", len(train.y), len(tq))
    tau = calibrate_tau(train)
    coef, intercept = fit(train, tau, sc.fusion.features)
    digest = train.hash()
    now = datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    model = FusionModel(VERSION, tuple(sc.fusion.features), tuple(coef), intercept, tau, digest,
                        now, split.to_json(), {})  # fmt: skip
    vq = training_queries(store, truth, split.valid_first, split.valid_last)
    valid = build_pairs(builder, vq, truth, split.t_grid)
    v = validate(model, valid)
    v["train_recall_at_5_t120_probers"] = recall_at(
        model.predict(train.X(tau, model.features)), train
    )
    model = replace(model, validation=v)
    cal = DtwCalibration(
        version="dtw-calibration-v1", tau=tau, n_pairs=len(train.y), n_positive=int(train.y.sum()),
        d_norm_same=_quantiles(train.d_norm[train.y == 1]),
        d_norm_other=_quantiles(train.d_norm[train.y == 0]), band_fraction=sc.dtw.band_fraction,
        anchor=[sc.dtw.anchor_before, sc.dtw.anchor_after], training_hash=digest, created_at=now,
    )  # fmt: skip
    out = Path(models_dir or cfg.app.paths.models)
    paths = [model.save(out / MODEL_FILE), cal.save(out / CALIBRATION_FILE)]
    summary = {"queries": len(tq), "pairs": len(train.y), "positives": int(train.y.sum())}
    return TrainSummary(model, cal, summary, paths, time.perf_counter() - t0)
