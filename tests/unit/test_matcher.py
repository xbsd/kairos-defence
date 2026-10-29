"""SPEC §10.1 and §10.8: the DTW matcher end to end on the P1 nights, with hand-set models."""

from __future__ import annotations

import math
import shutil
from datetime import datetime

import numpy as np
import pytest

from kairos_defense.features.build import windows_table
from kairos_defense.match.candidates import IndexStale, check_index
from kairos_defense.match.fusion import MODEL_FILE, ModelError
from kairos_defense.match.matcher import EXPLAIN_TOP, DtwMatcher
from kairos_defense.match.prefilter import WINDOWS_TABLE
from kairos_defense.match.query import load_query
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore

LIVE = "DEMO-BRAVO-0828-T1"


@pytest.fixture(scope="module")
def stores(toy_models):
    duck = DuckTrackStore(toy_models.app.paths.duckdb, toy_models.app)
    yield duck, LanceVectorStore(toy_models.app.paths.lancedb)
    duck.close()


@pytest.fixture(scope="module")
def matcher(toy_models, stores):
    return DtwMatcher(*stores, toy_models.scoring, toy_models.app.paths.models)


def test_dtw_matches_fields_and_order(toy_models, stores, matcher) -> None:
    res = matcher.match(load_query(stores[0], LIVE, 90, toy_models.scoring))
    ms = res.matches
    assert ms and len(ms) == len(res.baseline)
    scores = [m.score for m in ms]
    assert all(0.0 <= s <= 1.0 for s in scores) and scores == sorted(scores, reverse=True)
    order = list(toy_models.scoring.fusion.features)
    for i, m in enumerate(ms):
        assert m.query_incident_id == "DEMO-BRAVO-0828" and m.model_version == "fusion-v1"
        assert list(m.features) == [*order, "d_norm", "euclidean_d2", "window_s"]
        assert m.shape_sim == pytest.approx(m.features["shape_sim"])
        assert m.track_id and m.incident_id and m.installation_id and m.window_offset_s >= 0
        if i >= EXPLAIN_TOP:  # only the explained top 20 get a warp ratio and reasons
            assert math.isnan(m.warp_ratio) and m.reasons == []
    # in the top 20 a warp is NaN only when not credible (D-069); most have one
    assert sum(math.isfinite(m.warp_ratio) for m in ms[:EXPLAIN_TOP]) >= 10
    assert {m.track_id for m in ms} == {m.track_id for m in res.baseline}
    d = ms[0].to_dict()
    assert d["start_ts"] == ms[0].start_ts.isoformat()
    assert all(v is None or not (isinstance(v, float) and math.isnan(v)) for v in d.values())


def test_dtw_matcher_is_deterministic(toy_models, stores) -> None:
    a = DtwMatcher(*stores, toy_models.scoring, toy_models.app.paths.models)
    b = DtwMatcher(*stores, toy_models.scoring, toy_models.app.paths.models)
    for at in (45, 120):
        q = load_query(stores[0], LIVE, at, toy_models.scoring)
        ra, rb = a.match(q), b.match(q)
        assert [m.to_dict() for m in ra.matches] == [m.to_dict() for m in rb.matches]


def test_timings_are_reported(toy_models, stores, matcher) -> None:
    t = matcher.match(load_query(stores[0], LIVE, 90, toy_models.scoring)).timings
    stages = ("prefilter_ms", "signature_ms", "dtw_ms", "features_ms", "fusion_ms", "explain_ms")
    assert set(stages) | {"total_ms"} == set(t)
    assert all(t[k] >= 0 for k in t) and t["total_ms"] >= sum(t[k] for k in stages) * 0.99


def test_stale_index_is_refused(toy_models, stores, tmp_path) -> None:
    duck, lance = stores
    sc = toy_models.scoring
    probe = check_index(duck, lance, sc)  # the fixture's own index: fresh
    assert probe == duck.tracks_before(datetime(9999, 1, 1)).track_id[0]  # the earliest track
    window_mode = sc.model_copy(update={"windows": sc.windows.model_copy(
        update={"normalize": "window"})})  # fmt: skip
    with pytest.raises(IndexStale, match="make index"):  # built with another recipe
        check_index(duck, lance, window_mode)
    # every stored vector nudged: whichever window is probed, it no longer matches
    copy = tmp_path / "lancedb"
    shutil.copytree(toy_models.app.paths.lancedb, copy)
    other = LanceVectorStore(copy)
    tbl = other.to_pandas(WINDOWS_TABLE)
    vec = np.stack(tbl.vector.to_numpy()).astype(np.float32)
    vec[:, 0] += 0.01
    vec /= np.linalg.norm(vec, axis=1, keepdims=True)
    data = windows_table(tbl.drop(columns="vector").to_dict("records"), list(vec), vec.shape[1])
    other.replace(WINDOWS_TABLE, data)
    with pytest.raises(IndexStale):
        check_index(duck, other, sc)
    with pytest.raises(IndexStale):
        DtwMatcher(duck, other, sc, toy_models.app.paths.models)


def test_missing_models_are_refused(toy_models, p1_index, stores, tmp_path) -> None:
    with pytest.raises(ModelError, match="make models"):
        DtwMatcher(*stores, toy_models.scoring, p1_index.cfg.app.paths.models)  # empty folder
    folder = tmp_path / "m"
    shutil.copytree(toy_models.app.paths.models, folder)
    (folder / MODEL_FILE).unlink()
    with pytest.raises(ModelError, match="make models"):
        DtwMatcher(*stores, toy_models.scoring, folder)


def test_live_top3_are_p1_on_the_p1_nights(toy_models, stores, matcher) -> None:
    """A fixture check with the hand-set model; the exact three are the eval's and gate's job."""
    res = matcher.match(load_query(stores[0], LIVE, 90, toy_models.scoring))
    top = res.matches[:3]
    assert all(m.incident_id.startswith("P1-") for m in top), [m.incident_id for m in top]
    assert all(m.reasons for m in top) and "Same RF family (FAM-07)" in top[0].reasons
