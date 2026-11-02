"""The live-mode store and the composite ports (D-172): views, unions, merge, reset, truth."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from kairos_defense.store.composite import CompositeTrackStore, CompositeVectorStore, is_live_id
from kairos_defense.store.guard import TruthAccessError
from kairos_defense.store.lance import LanceVectorStore
from kairos_defense.store.live_feed import RESET_TABLES, DuckFeedStore

SENSORS = pd.DataFrame([
    {"sensor_id": "BRAVO-RADAR-1", "installation_id": "BRAVO", "kind": "radar", "x_m": 22000.0,
     "y_m": -6000.0, "range_m": 3500.0, "params": "{}"},
    {"sensor_id": "BRAVO-RF-1", "installation_id": "BRAVO", "kind": "rf", "x_m": 22200.0,
     "y_m": -5850.0, "range_m": 4000.0, "params": "{}"},
])  # fmt: skip
T = datetime(2026, 9, 2, 2, 0, 0)


def _points(tid: str, inc: str, n: int, t0=T, x0=22000.0) -> list[dict]:
    return [{"incident_id": inc, "track_id": tid, "installation_id": "BRAVO",
             "region_id": "COASTAL", "sensor_id": "BRAVO-RADAR-1",
             "ts": t0 + pd.Timedelta(seconds=k), "x_m": x0 + 10 * k, "y_m": -6500.0,
             "alt_m": 100.0, "quality": 0.9} for k in range(n)]  # fmt: skip


@pytest.fixture
def feed(cfg, tmp_path):
    with DuckFeedStore(tmp_path / "lm", cfg.app, sensors=SENSORS) as f:
        yield f


def test_detections_go_to_live_tables_and_the_views_read_them(feed) -> None:
    st = feed.append("live_points", _points("LIVE-B-1-T1", "LIVE-B-1", 30))
    assert (st.table, st.rows, st.total_rows) == ("live_points", 30, 30)
    assert st.statement == "INSERT INTO live_points … 30 rows" and st.write_ms >= 0
    rf = [{"installation_id": "BRAVO", "sensor_id": "BRAVO-RF-1", "ts": T + pd.Timedelta(seconds=k),
           "band": "2.4GHz", "protocol_family": "FAM-07", "bearing_deg": 200.0, "snr_db": 20.0}
          for k in range(0, 30, 2)]  # fmt: skip
    feed.append("live_rf", rf)
    assert len(feed.track_points("LIVE-B-1-T1")) == 30  # the track_points view
    ctx = feed.sensor_context_until("LIVE-B-1-T1", T + pd.Timedelta(seconds=10))
    assert ctx["rf_family"] == "FAM-07"  # the §11.2 SQL ran on the live rows and the sensors copy
    with pytest.raises(ValueError, match="not a live detection table"):
        feed.append("track_points", [])


def test_incidents_tracks_results_and_learned_rows(feed) -> None:
    row = {
        "incident_id": "LIVE-B-1",
        "installation_id": "BRAVO",
        "region_id": "COASTAL",
        "start_ts": T,
        "end_ts": T,
        "n_tracks": 1,
        "is_swarm": False,
        "state": "open",
    }
    feed.put_incident(row)
    feed.put_incident({**row, "state": "closed", "n_tracks": 2})
    inc = feed.incident("LIVE-B-1")
    assert inc["state"] == "closed" and inc["n_tracks"] == 2 and inc["source"] == "live"
    assert feed.sql("SELECT count(*) AS n FROM incidents")["n"].iloc[0] == 1
    with pytest.raises(ValueError, match="state"):
        feed.put_incident({**row, "state": "gone"})
    feed.put_track({"track_id": "LIVE-B-1-T1", "incident_id": "LIVE-B-1",
                    "installation_id": "BRAVO", "region_id": "COASTAL",
                    "sensor_track_id": "TRK-9", "start_ts": T, "end_ts": T,
                    "n_points": 3})  # fmt: skip
    assert feed.live_tracks("LIVE-B-1")["sensor_track_id"].tolist() == ["TRK-9"]
    feed.add_result({"incident_id": "LIVE-B-1", "track_id": "LIVE-B-1-T1", "t_s": 50,
                     "kind": "track", "computed_ts": T, "model_version": "m", "elapsed_ms": 1.0,
                     "matches": [{"rank": 1, "track_id": "X"}]})  # fmt: skip
    feed.add_result({"incident_id": "LIVE-B-1", "track_id": "LIVE-B-1-T1", "t_s": 45,
                     "kind": "track", "computed_ts": T, "model_version": "m", "elapsed_ms": 1.0,
                     "matches": []})  # fmt: skip
    assert [r["t_s"] for r in feed.results("LIVE-B-1")] == [45, 50]
    assert feed.results("LIVE-B-1")[1]["matches"] == [{"rank": 1, "track_id": "X"}]


def test_reset_empties_every_live_table(feed) -> None:
    feed.append("live_points", _points("LIVE-B-1-T1", "LIVE-B-1", 5))
    feed.put_incident({"incident_id": "LIVE-B-1", "installation_id": "BRAVO",
                       "region_id": "COASTAL", "start_ts": T, "end_ts": T, "n_tracks": 1,
                       "is_swarm": False, "state": "closed"})  # fmt: skip
    out = feed.reset()
    assert out["live_points"] == 5 and out["live_incidents"] == 1
    assert set(out) == set(RESET_TABLES)
    assert all(v == 0 for v in feed.counts().values())
    assert len(feed.sql("SELECT * FROM sensors")) == 2  # the copy of the history's sensors stays


def test_feed_store_refuses_the_truth_path(cfg, tmp_path) -> None:
    truth = tmp_path / "gt"
    app = cfg.app.model_copy(update={"paths": cfg.app.paths.model_copy(
        update={"truth": truth / "feed.duckdb"})})  # fmt: skip
    with pytest.raises(TruthAccessError):
        DuckFeedStore(truth, app)


class Fake:
    """A ``TrackStore`` with canned signatures and features."""

    def __init__(self, sigs: pd.DataFrame, feats: pd.DataFrame) -> None:
        self.sigs, self.feats = sigs, feats

    def tracks_before(self, ts, exclude_incident=None):
        s = self.sigs[self.sigs["start_ts"] < ts].sort_values(["start_ts", "track_id"])
        return s if exclude_incident is None else s[s["incident_id"] != exclude_incident]

    def features_many(self, ids):
        return self.feats[self.feats["track_id"].isin(ids)]

    def signature(self, tid):
        return {"track_id": tid, "owner": "live" if is_live_id(tid) else "main"}

    def sql(self, q, p=None):
        return pd.DataFrame({"q": [q]})


def test_composite_unions_in_time_order_and_routes_by_owner() -> None:
    main = Fake(pd.DataFrame({"track_id": ["H-2", "H-1"], "incident_id": ["H", "H"],
                              "start_ts": [T - pd.Timedelta(days=2), T - pd.Timedelta(days=9)]}),
                pd.DataFrame({"track_id": ["H-1", "H-1"], "t_s": [1, 0]}))  # fmt: skip
    live = Fake(pd.DataFrame({"track_id": ["LIVE-A-T1", "LIVE-B-T1"], "incident_id": ["A", "B"],
                              "start_ts": [T - pd.Timedelta(hours=1), T + pd.Timedelta(hours=1)]}),
                pd.DataFrame({"track_id": ["LIVE-A-T1"], "t_s": [0]}))  # fmt: skip
    c = CompositeTrackStore(main, live)
    before = c.tracks_before(T)
    assert before["track_id"].tolist() == ["H-1", "H-2", "LIVE-A-T1"]  # LIVE-B started later
    assert c.tracks_before(T, "A")["track_id"].tolist() == ["H-1", "H-2"]
    f = c.features_many(["LIVE-A-T1", "H-1"])
    assert list(zip(f["track_id"], f["t_s"], strict=True)) == [("H-1", 0), ("H-1", 1),
                                                                ("LIVE-A-T1", 0)]  # fmt: skip
    assert c.signature("LIVE-A-T1")["owner"] == "live" and c.signature("H-1")["owner"] == "main"
    assert c.context_asof("LIVE-A-T1").empty


def test_composite_vector_search_merges_by_distance(tmp_path) -> None:
    import pyarrow as pa

    def table(ids, vecs):
        flat = pa.array(np.asarray(vecs, np.float32).ravel(), pa.float32())
        return pa.table({"window_id": ids, "incident_id": ids,
                         "window_s": pa.array([60] * len(ids), pa.int32()),
                         "start_ts_ms": pa.array([0] * len(ids), pa.int64()),
                         "vector": pa.FixedSizeListArray.from_arrays(flat, 2)})  # fmt: skip

    main = LanceVectorStore(tmp_path / "main")
    main.replace("flight_windows", table(["h1", "h2"], [[1, 0], [0, 1]]))
    live = LanceVectorStore(tmp_path / "live")
    c = CompositeVectorStore(main, live)
    q = np.array([0.9, 0.1], np.float32)
    assert c.search("flight_windows", q, None, 5)["window_id"].tolist() == ["h1", "h2"]
    c.upsert("flight_windows", [{"window_id": "LIVE-x", "incident_id": "LIVE-x", "window_s": 60,
                                 "start_ts_ms": 0, "vector": np.array([0.9, 0.1])}])  # fmt: skip
    assert not main.to_pandas("flight_windows")["window_id"].str.startswith("LIVE").any()
    hits = c.search("flight_windows", q, "incident_id != 'h2'", 5)
    assert hits["window_id"].tolist() == ["LIVE-x", "h1"]
    assert hits["_distance"].is_monotonic_increasing
    assert live.drop("flight_windows") == 1 and not live.has("flight_windows")
