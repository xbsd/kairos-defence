"""CLAUDE.md rule 3 and SPEC §10.3: a search for past flights only ever returns flights that
started before the query flight, never the query's own incident, and the query itself never sees
points after T. Written before the matcher (phase 3 prompt)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.channels import load_site
from kairos_defense.match.baseline import euclidean_matches
from kairos_defense.match.prefilter import LookAheadError, prefilter, window_filter
from kairos_defense.match.query import load_query, query_at
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore

T_GRID = (45, 90, 180)


@pytest.fixture
def stores(p1_index):
    duck = DuckTrackStore(p1_index.cfg.app.paths.duckdb, p1_index.cfg.app)
    yield duck, LanceVectorStore(p1_index.cfg.app.paths.lancedb)
    duck.close()


def test_filter_text() -> None:
    flt = window_filter(120, 1_777_000_000_000, "P1-DELTA-260419")
    assert "window_s = 120" in flt
    assert "start_ts_ms < 1777000000000" in flt
    assert "incident_id != 'P1-DELTA-260419'" in flt
    with pytest.raises(ValueError):
        window_filter(120, 0, "x' OR '1'='1")


def test_results_never_start_after_the_query(p1_index, stores) -> None:
    duck, lance = stores
    sc = p1_index.cfg.scoring
    tracks = duck.tracks()
    later_p1 = 0
    for row in tracks.itertuples():
        for at in T_GRID:
            q = load_query(duck, row.track_id, at, sc)
            assert q.start_ts == row.start_ts  # T counts from the first radar point (D-050)
            matches = euclidean_matches(q, lance, sc)
            for m in matches:
                assert m.start_ts < q.start_ts, (row.track_id, at, m.track_id)
                assert m.incident_id != q.incident_id
            if row.track_id == "P1-ALPHA-260303-T1":
                later = tracks[
                    (tracks.start_ts > q.start_ts) & tracks.incident_id.str.startswith("P1-")
                ]
                later_p1 += len(later)
                assert not {m.track_id for m in matches} & set(later.track_id)
    assert later_p1 > 0  # later P1 flights were in the index and still never returned


def test_first_track_has_no_history(p1_index, stores) -> None:
    duck, lance = stores
    first = duck.tracks().sort_values("start_ts").iloc[0]
    q = load_query(duck, first.track_id, 90, p1_index.cfg.scoring)
    assert euclidean_matches(q, lance, p1_index.cfg.scoring) == []


def test_query_ignores_points_after_t(p1_index, stores) -> None:
    duck, _ = stores
    pts = duck.track_points("DEMO-BRAVO-0828-T1")
    site = load_site(duck, "BRAVO")
    ids = {"track_id": "DEMO-BRAVO-0828-T1", "incident_id": "DEMO-BRAVO-0828"}
    sc = p1_index.cfg.scoring
    for at in T_GRID:
        q = query_at(pts, site, at, sc, ids)
        cut = pts.ts.iloc[0] + pd.Timedelta(seconds=at)
        tampered = pts.copy()
        after = tampered.ts > cut
        assert after.any()
        tampered.loc[after, ["x_m", "y_m"]] += 5000.0  # the future, wildly different
        tampered.loc[after, "alt_m"] = 15.0
        q2 = query_at(tampered, site, at, sc, ids)
        assert np.array_equal(q.vector, q2.vector)
        assert q.target.asset_id == q2.target.asset_id
        assert q.features.ts.max() <= cut and len(q.features) <= at + 1


class LeakyStore:
    """A VectorStore that ignores the filter and returns a row from the future."""

    def __init__(self, start_ms: int) -> None:
        self.start_ms = start_ms

    def upsert(self, table, rows) -> None:  # pragma: no cover - protocol filler
        raise NotImplementedError

    def search(self, table, vector, where, k) -> pd.DataFrame:
        return pd.DataFrame({
            "window_id": ["F-T1:60:0"], "track_id": ["F-T1"], "incident_id": ["F"],
            "installation_id": ["ALPHA"], "window_s": [60], "offset_s": [0],
            "start_ts_ms": [self.start_ms + 1000], "_distance": [0.0],
        })  # fmt: skip


def test_prefilter_refuses_a_leaky_store(p1_index, stores) -> None:
    duck, _ = stores
    q = load_query(duck, "P1-DELTA-260419-T1", 90, p1_index.cfg.scoring)
    with pytest.raises(LookAheadError):
        prefilter(q, LeakyStore(q.start_ms), p1_index.cfg.scoring)
