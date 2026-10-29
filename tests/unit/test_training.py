"""SPEC §10.6 fusion training (D-073, D-078). It lives in ``kairos_defense.eval``, so it may read
truth; the P1 nights stand in for the training months via ``TrainSplit``."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from kairos_defense.eval.training import (
    QUERY_KINDS,
    Pairs,
    TrainSplit,
    build_pairs,
    calibrate_tau,
    train_models,
    training_queries,
)
from kairos_defense.eval.truth import track_truth
from kairos_defense.match.candidates import CandidateBuilder
from kairos_defense.match.fusion import CALIBRATION_FILE, MODEL_FILE, FusionModel
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore

SPLIT = TrainSplit(train_last=date(2026, 5, 31), valid_first=date(2026, 6, 1), t_grid=(60, 120))


@pytest.fixture(scope="module")
def ctx(p1_index):
    cfg = p1_index.cfg
    duck = DuckTrackStore(cfg.app.paths.duckdb, cfg.app)
    yield cfg, duck, LanceVectorStore(cfg.app.paths.lancedb), track_truth(cfg.app)
    duck.close()


@pytest.fixture(scope="module")
def trained(ctx, tmp_path_factory):
    cfg, duck, lance, truth = ctx
    return train_models(cfg, duck, lance, truth, SPLIT, tmp_path_factory.mktemp("models"))


def test_pairs_respect_time_and_split(ctx) -> None:
    cfg, duck, lance, truth = ctx
    queries = training_queries(duck, truth, SPLIT.train_first, SPLIT.train_last)
    assert queries and all(SPLIT.train_first <= q.night <= SPLIT.train_last for q in queries)
    assert {q.actor_type for q in queries} <= set(QUERY_KINDS)  # no swarm drones (D-078)
    assert "P1-ALPHA-260303-T1" in {q.track_id for q in queries}
    pairs = build_pairs(CandidateBuilder(duck, lance, cfg.scoring), queries, truth, SPLIT.t_grid)
    tracks = duck.tracks().set_index("track_id")
    starts, status = tracks["start_ts"], tracks["status"]
    k = pairs.keys
    assert (starts.loc[k.track_id].to_numpy() < starts.loc[k["query"]].to_numpy()).all()
    assert (status.loc[k.track_id] == "history").all() and (
        status.loc[k["query"]] == "history"
    ).all()
    actor = truth.set_index("track_id")["actor_id"]
    same = actor.loc[k.track_id].to_numpy() == actor.loc[k["query"]].to_numpy()
    assert np.array_equal(pairs.y, same.astype(np.int8)) and pairs.y.sum() > 0
    assert pairs.context.shape == (len(k), 6) and np.isfinite(pairs.context).all()
    assert set(k.at_s) <= set(SPLIT.t_grid)
    assert list(k.sort_values(["query", "at_s", "track_id"]).index) == list(k.index)  # sorted


def test_tau_is_the_median_same_actor_d_norm() -> None:
    keys = pd.DataFrame({"query": ["q"] * 5, "actor_type": "prober", "at_s": 60,
                         "track_id": list("abcde"), "answerable": True})  # fmt: skip
    p = Pairs(keys, np.zeros((5, 6)), np.array([1.0, 2.0, 9.0, 3.0, 0.1]),
              np.array([1, 1, 0, 1, 0], dtype=np.int8))  # fmt: skip
    assert calibrate_tau(p) == 2.0
    with pytest.raises(ValueError, match="same-actor"):
        calibrate_tau(Pairs(keys, p.context, p.d_norm, np.zeros(5, dtype=np.int8)))
    X = p.X(2.0, ["shape_sim", "rf_match"])
    assert np.allclose(X[:, 0], np.exp(-p.d_norm / 2.0)) and np.allclose(X[:, 1], 0.0)


def test_training_is_deterministic(ctx, trained, tmp_path) -> None:
    cfg, duck, lance, truth = ctx
    again = train_models(cfg, duck, lance, truth, SPLIT, tmp_path)
    assert again.model.training_hash == trained.model.training_hash
    assert again.model.coefficients == trained.model.coefficients
    assert again.model.intercept == trained.model.intercept and again.model.tau == trained.model.tau
    assert again.calibration.d_norm_same == trained.calibration.d_norm_same


def test_artifacts_written_and_loadable(cfg, trained) -> None:
    folder = trained.paths[0].parent
    model = json.loads((folder / MODEL_FILE).read_text())
    cal = json.loads((folder / CALIBRATION_FILE).read_text())
    for key in (
        "version",
        "created_at",
        "features",
        "coefficients",
        "intercept",
        "tau",
        "training_hash",
        "train_split",
        "validation",
    ):
        assert key in model, key  # fmt: skip
    for key in (
        "tau",
        "n_pairs",
        "n_positive",
        "d_norm_same",
        "d_norm_other",
        "band_fraction",
        "anchor",
        "training_hash",
        "created_at",
    ):
        assert key in cal, key  # fmt: skip
    assert model["tau"] == cal["tau"] and model["training_hash"] == cal["training_hash"]
    assert model["train_split"]["train_last"] == "2026-05-31"
    assert {"queries", "pairs", "positives"} <= set(model["validation"])
    loaded = FusionModel.load(folder / MODEL_FILE, cfg.scoring.fusion.features)
    assert loaded.version == "fusion-v1" and len(loaded.coefficients) == 7
    assert trained.train["positives"] > 0 and trained.calibration.n_pairs == trained.train["pairs"]
