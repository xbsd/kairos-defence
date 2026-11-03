"""The matcher trace (D-187): identical results with and without it, its order, counts and
fields, and its measured overhead. On the P1 nights with the hand-set models."""

from __future__ import annotations

import json
import math
import time

import numpy as np
import pytest

from kairos_defense.match import dtw_rerank
from kairos_defense.match.matcher import DtwMatcher
from kairos_defense.match.query import load_query
from kairos_defense.match.trace import MAX_POINTS, THUMB, TRACE_PATHS, downsample_path, thumbnail
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore

QUERIES = ("DEMO-BRAVO-0828-T1", "P1-DELTA-260419-T1")


@pytest.fixture(scope="module")
def matcher(toy_models):
    duck = DuckTrackStore(toy_models.app.paths.duckdb, toy_models.app)
    m = DtwMatcher(duck, LanceVectorStore(toy_models.app.paths.lancedb), toy_models.scoring,
                   toy_models.app.paths.models)  # fmt: skip
    yield m, duck, toy_models.scoring
    duck.close()


def _result(res) -> list:
    return [m.to_dict() for m in res.matches], [m.to_dict() for m in res.baseline]


@pytest.mark.parametrize("track", QUERIES)
@pytest.mark.parametrize("at", [60, 120, 180])
def test_trace_on_and_off_give_identical_matches(matcher, track, at) -> None:
    m, duck, sc = matcher
    q = load_query(duck, track, at, sc)
    plain = m.match(q)
    traced = m.match(q, trace=True)
    assert plain.trace is None and traced.trace is not None
    assert _result(plain) == _result(traced)  # tracks, scores, features, reasons, warp ratios
    assert json.dumps(traced.trace, allow_nan=False)  # JSON-safe


@pytest.fixture(scope="module")
def traced(matcher):
    m, duck, sc = matcher
    q = load_query(duck, QUERIES[0], 120, sc)
    return m, sc, q, m.match(q, trace=True)


def test_trace_order_counts_and_fields(traced) -> None:
    m, sc, q, res = traced
    t = res.trace
    n_c = len(res.matches)
    p, d, f = t["prefilter"], t["dtw"], t["fusion"]
    assert t["query"]["track_id"] == q.track_id and t["query"]["at_s"] == 120
    assert t["query"]["n"] == q.rows_used and len(t["query"]["curve"]) <= MAX_POINTS
    assert p["candidates"] == n_c > 0 and p["k_windows"] == sc.prefilter.k_windows
    for col in ("track_id", "incident_id", "start_ts_ms", "distance", "window_s", "offset_s"):
        assert len(p[col]) == n_c, col
    assert p["distance"] == sorted(p["distance"])  # prefilter order: nearest first
    assert [b.track_id for b in res.baseline] == p["track_id"]
    for col in ("distance", "d_norm", "band", "m", "ms_each", "shape_sim"):
        assert len(d[col]) == n_c, col
    n = d["n"]
    for k in range(n_c):
        assert d["distance"][k] == pytest.approx(d["d_norm"][k] * math.sqrt(n), rel=1e-4)
        assert d["shape_sim"][k] == pytest.approx(math.exp(-d["d_norm"][k] / m.tau), rel=1e-4)
        assert d["band"][k] == dtw_rerank.band_window(n, d["m"][k], sc.dtw.band_fraction)
    assert len(d["detail"]) == min(TRACE_PATHS, n_c)
    assert [x["order"] for x in d["detail"]] == list(range(len(d["detail"])))
    for x in d["detail"]:
        assert x["track_id"] == p["track_id"][x["order"]]
        path = np.asarray(x["path"])
        assert 2 <= len(path) <= MAX_POINTS and x["path_len"] >= len(path)
        assert path[0][0] == 0 and path[-1][0] == n - 1  # every query sample is aligned
        assert (np.diff(path, axis=0) >= 0).all()  # monotone
        assert path[:, 1].max() < d["m"][x["order"]]
        assert len(x["cost"]) == THUMB and all(len(r) == THUMB for r in x["cost"])
        assert len(x["curve"]) <= MAX_POINTS
    assert f["features"] == list(m.model.features) and len(f["values"]) == n_c
    by_track = {mm.track_id: mm.score for mm in res.matches}
    for tid, s in zip(p["track_id"], f["score"], strict=True):
        assert s == pytest.approx(by_track[tid], abs=1e-6)  # rounded to 6 decimals
    assert [r["track_id"] for r in t["ranking"]] == [mm.track_id for mm in res.matches[:10]]
    assert t["ranking"][0]["reasons"] == res.matches[0].reasons


def test_trace_overhead_is_measured(traced, capsys) -> None:
    m, _sc, q, res = traced
    t = res.trace
    assert t["trace_ms"] > 0
    assert t["total_ms"] == pytest.approx(res.timings["total_ms"], rel=1e-3)
    assert t["dtw"]["ms"] == pytest.approx(res.timings["dtw_ms"], rel=1e-3)
    t0 = time.perf_counter()
    m.match(q)
    plain = (time.perf_counter() - t0) * 1e3
    t0 = time.perf_counter()
    m.match(q, trace=True)
    traced_ms = (time.perf_counter() - t0) * 1e3
    with capsys.disabled():
        print(
            f"\nmatcher trace overhead: {t['trace_ms']:.1f} ms recorded; "
            f"{plain:.1f} ms plain, {traced_ms:.1f} ms traced (wall)"
        )


def test_downsampling_and_thumbnails() -> None:
    path = np.column_stack([np.arange(200), np.arange(200) // 2])
    small = downsample_path(path, 10)
    assert len(small) == 10 and small[0] == [0, 0] and small[-1] == [199, 99]
    assert downsample_path(path[:5], 10) == path[:5].tolist()
    cost = np.arange(36, dtype=float).reshape(6, 6)
    cost[0, 5] = np.inf
    th = thumbnail(cost, 3)
    assert th == [[0.0, 2.0, 4.0], [12.0, 14.0, 16.0], [24.0, 26.0, 28.0]]
    assert thumbnail(np.full((2, 2), np.inf), 2) == [[None, None], [None, None]]


def test_the_path_cutoff_and_the_top10_paths(matcher, monkeypatch) -> None:
    from functools import partial

    from kairos_defense.match import matcher as matcher_mod
    from kairos_defense.match.trace import TraceRecorder

    m, duck, sc = matcher
    monkeypatch.setattr(matcher_mod, "TraceRecorder", partial(TraceRecorder, paths=3))
    q = load_query(duck, QUERIES[0], 120, sc)
    res = m.match(q, trace=True)
    d, p = res.trace["dtw"], res.trace["prefilter"]
    top = {p["track_id"].index(mm.track_id) for mm in res.matches[:10]}
    assert {x["order"] for x in d["detail"]} == {0, 1, 2} | top
    assert [x["order"] for x in d["detail"]] == sorted(x["order"] for x in d["detail"])
    assert res.trace["trace_paths"] == 3
