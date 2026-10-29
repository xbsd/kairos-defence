"""DuckDB adapter: §11 context joins, RF/Remote ID association (D-048), §11.3 history query."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from kairos_defense.store.ddl import DERIVED_COLUMNS, RAW_COLUMNS, RAW_DDL
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.guard import TruthAccessError, connect_app_db

T0 = datetime(2026, 5, 3, 2, 0, 0)


def _frame(name: str, rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=RAW_COLUMNS[name])


def _track(tid: str, inc: str, bearing: float, dist: float, t0: datetime, n: int) -> list[dict]:
    b = np.radians(bearing)
    return [{"incident_id": inc, "track_id": tid, "installation_id": "TEST", "region_id": "R",
             "sensor_id": "TEST-RADAR-1", "ts": t0 + timedelta(seconds=i),
             "x_m": dist * np.sin(b), "y_m": dist * np.cos(b), "alt_m": 100.0, "quality": 0.9}
            for i in range(n)]  # fmt: skip


@pytest.fixture
def tiny(cfg, tmp_path):
    """Track A (north, 0-120 s) and B (east, 30-150 s) overlap at one base; C is later, alone."""
    tables = {
        "regions": _frame("regions", [{"region_id": "R", "utc_offset_hours": -5}]),
        "installations": _frame("installations", [{"installation_id": "TEST", "name": "T",
            "region_id": "R", "origin_x_m": 0.0, "origin_y_m": 0.0, "rotation_deg": 0.0,
            "fence_wkt": "POLYGON ((-1 -1, 1 -1, 1 1, -1 1, -1 -1))"}]),
        "sensors": _frame("sensors", [{"sensor_id": "TEST-RF-1", "installation_id": "TEST",
            "kind": "rf", "x_m": 0.0, "y_m": 0.0, "range_m": 4000.0, "params": "{}"}]),
        "incidents": _frame("incidents", [
            {"incident_id": i, "installation_id": "TEST", "region_id": "R", "start_ts": T0,
             "end_ts": T0, "n_tracks": 1, "is_swarm": False, "status": "history"}
            for i in ("IA", "IB", "IC")]),
        "track_points": _frame("track_points",
            _track("IA-T1", "IA", 0.0, 1000.0, T0, 121)
            + _track("IB-T1", "IB", 90.0, 1000.0, T0 + timedelta(seconds=30), 121)
            + _track("IC-T1", "IC", 0.0, 1000.0, T0 + timedelta(hours=2), 61)),
        "rf_detections": _frame("rf_detections",
            [{"installation_id": "TEST", "sensor_id": "TEST-RF-1", "ts": T0 + timedelta(seconds=s),
              "band": "2.4GHz", "protocol_family": "FAM-07", "bearing_deg": 1.0, "snr_db": 20.0}
             for s in range(0, 121, 2)]
            + [{"installation_id": "TEST", "sensor_id": "TEST-RF-1",
                "ts": T0 + timedelta(seconds=s), "band": "2.4GHz", "protocol_family": "FAM-02",
                "bearing_deg": 89.0, "snr_db": 20.0}
               for s in range(30, 151, 2)]
            + [{"installation_id": "TEST", "sensor_id": "TEST-RF-1",
                "ts": T0 + timedelta(hours=2, seconds=s), "band": "900MHz",
                "protocol_family": "FAM-21", "bearing_deg": 200.0, "snr_db": 9.0}
               for s in (-25, 85, 200)]),  # IC: two within ±30 s (no gate when alone), one not
        "remote_id": _frame("remote_id",
            [{"installation_id": "TEST", "ts": T0 + timedelta(seconds=s), "serial": "SN-A",
              "drone_x_m": 30.0, "drone_y_m": 1000.0, "op_x_m": -50.0, "op_y_m": 3000.0}
             for s in range(0, 121)]
            + [{"installation_id": "TEST", "ts": T0 + timedelta(seconds=60), "serial": "SN-FAR",
                "drone_x_m": 250.0, "drone_y_m": 1000.0, "op_x_m": 0.0, "op_y_m": 0.0}]),
        "weather": _frame("weather", [
            {"region_id": "R", "ts": T0 - timedelta(hours=1), "wind_ms": 3.0, "wind_dir_deg": 10.0,
             "visibility_km": 9.0},
            {"region_id": "R", "ts": T0 + timedelta(seconds=60), "wind_ms": 7.0,
             "wind_dir_deg": 20.0, "visibility_km": 8.0}]),
        "base_events": _frame("base_events", [
            {"installation_id": "TEST", "start_ts": T0 + timedelta(seconds=100),
             "end_ts": T0 + timedelta(hours=1), "kind": "exercise", "label": "x"}]),
    }  # fmt: skip
    path = tmp_path / "tiny.duckdb"
    con = connect_app_db(path, cfg.app)
    for name, ddl in RAW_DDL.items():
        con.execute(ddl)
        if name in tables:
            con.register("df_in", tables[name])
            con.execute(f"INSERT INTO {name} SELECT * FROM df_in")
            con.unregister("df_in")
    con.close()
    store = DuckTrackStore(path, cfg.app, read_only=False)
    yield store
    store.close()


def test_rf_bearing_gate_separates_concurrent_tracks(tiny) -> None:
    rf = tiny.rf_association()
    fams = rf.groupby("track_id").protocol_family.apply(set).to_dict()
    assert fams["IA-T1"] == {"FAM-07"} and fams["IB-T1"] == {"FAM-02"}
    ic = rf[rf.track_id == "IC-T1"]
    assert ic.protocol_family.tolist() == ["FAM-21"] and ic.n.tolist() == [2]  # alone: no gate


def test_rid_within_5s_and_100m(tiny) -> None:
    rid = tiny.rid_association()
    assert set(rid.track_id) == {"IA-T1"}
    assert rid.serial.tolist() == ["SN-A"]  # SN-FAR is 250 m off the track
    ctx = tiny.sensor_context()
    assert ctx["IA-T1"].rid_stable and ctx["IA-T1"].rid_operator_xy == (-50.0, 3000.0)
    assert ctx["IA-T1"].rf_family == "FAM-07" and ctx["IB-T1"].rid_serials == ()
    assert tiny.sensor_context(["IB-T1"]).keys() == {"IB-T1"}


def test_context_asof_and_events(tiny) -> None:
    f = pd.DataFrame({c: [None] * 121 for c in DERIVED_COLUMNS["track_features"]})
    f["track_id"], f["incident_id"], f["installation_id"] = "IA-T1", "IA", "TEST"
    f["t_s"] = np.arange(121, dtype=np.int32)
    f["ts"] = [T0 + timedelta(seconds=i) for i in range(121)]
    f["speed_ms"] = 10.0
    f = f.astype({c: "float64" for c in DERIVED_COLUMNS["track_features"][5:-1]})
    f["in_gap"] = False
    tiny.write_table("track_features", f)
    ctx = tiny.context_asof("IA-T1")
    assert len(ctx) == 121
    assert ctx.wind_ms.iloc[59] == 3.0 and ctx.wind_ms.iloc[60] == 7.0  # as of, not nearest
    assert pd.isna(ctx.base_events.iloc[99]) and ctx.base_events.iloc[100] == "exercise"


def test_tracks_before_is_strict_and_excludes_incident(tiny) -> None:
    rows = [{c: None for c in DERIVED_COLUMNS["track_signatures"]} for _ in range(3)]
    for r, (tid, inc, dt) in zip(rows, [("IA-T1", "IA", 0), ("IB-T1", "IB", 30),
                                        ("IC-T1", "IC", 7200)], strict=True):  # fmt: skip
        r.update(track_id=tid, incident_id=inc, start_ts=T0 + timedelta(seconds=dt),
                 end_ts=T0 + timedelta(seconds=dt + 120), duration_s=120.0, loiter_dir="none",
                 rf_family="unknown", rid_present=False, tod_minutes=1260)  # fmt: skip
    tiny.write_table(
        "track_signatures", pd.DataFrame(rows, columns=DERIVED_COLUMNS["track_signatures"])
    )
    before = tiny.tracks_before(T0 + timedelta(seconds=30))
    assert before.track_id.tolist() == ["IA-T1"]  # IB started exactly then: not before
    assert tiny.tracks_before(T0 + timedelta(hours=3), exclude_incident="IB").track_id.tolist() == [
        "IA-T1", "IC-T1"]  # fmt: skip
    assert tiny.signature("IC-T1")["incident_id"] == "IC"
    with pytest.raises(KeyError):
        tiny.signature("nope")


def test_write_table_checks_columns(tiny) -> None:
    with pytest.raises(ValueError):
        tiny.write_table("track_features", pd.DataFrame({"x": [1]}))
    with pytest.raises(ValueError):
        tiny.write_table("track_points", pd.DataFrame())


def test_adapter_refuses_truth(cfg) -> None:
    with pytest.raises(TruthAccessError):
        DuckTrackStore(cfg.app.paths.truth, cfg.app)


def _add_rf(store, rows: list[tuple[int, str, float]]) -> None:
    """Extra RF detections at T0 + s seconds: (s, family, bearing)."""
    df = pd.DataFrame([{"installation_id": "TEST", "sensor_id": "TEST-RF-1",
                        "ts": T0 + timedelta(seconds=s), "band": "2.4GHz", "protocol_family": fam,
                        "bearing_deg": brg, "snr_db": 20.0} for s, fam, brg in rows],
                      columns=RAW_COLUMNS["rf_detections"])  # fmt: skip
    store.con.register("df_in", df)
    store.con.execute("INSERT INTO rf_detections SELECT * FROM df_in")
    store.con.unregister("df_in")


def test_sensor_context_until_is_bounded(tiny) -> None:
    """D-071: RF and Remote ID heard after ``until`` never change the partial context; before it
    they do."""
    full = tiny.sensor_context_until("IA-T1", T0 + timedelta(hours=1))
    assert full == {"rf_family": "FAM-07", "rid_serials": ("SN-A",),
                    "rid_operator_xy": (-50.0, 3000.0)}  # fmt: skip
    early = tiny.sensor_context_until("IA-T1", T0 + timedelta(seconds=20))
    assert early == full
    _add_rf(tiny, [(s, "FAM-30", 1.0) for s in range(21, 121)])  # a louder family, later
    assert tiny.sensor_context_until("IA-T1", T0 + timedelta(seconds=20)) == early
    assert tiny.sensor_context_until("IA-T1", T0 + timedelta(hours=1))["rf_family"] == "FAM-30"
    _add_rf(tiny, [(s, "FAM-30", 1.0) for s in range(0, 20)] * 2)  # before T: it counts
    assert tiny.sensor_context_until("IA-T1", T0 + timedelta(seconds=20))["rf_family"] == "FAM-30"
    none = tiny.sensor_context_until("IA-T1", T0 - timedelta(seconds=1))  # nothing seen yet
    assert none == {"rf_family": "unknown", "rid_serials": (), "rid_operator_xy": None}


def test_concurrency_uses_only_tracks_seen_by_until(tiny) -> None:
    """IB starts at T0+30 s. At T0+20 s nobody knows it will fly, so IA is alone and its RF is not
    bearing-gated; over the full span the gate drops the off-bearing detection."""
    _add_rf(tiny, [(10, "FAM-02", 89.0)])
    early = tiny.rf_association(["IA-T1"], until=T0 + timedelta(seconds=20))
    assert dict(zip(early.protocol_family, early.n, strict=True)) == {"FAM-07": 11, "FAM-02": 1}
    full = tiny.rf_association(["IA-T1"])
    assert set(full.protocol_family) == {"FAM-07"}  # concurrent with IB: gated
    assert tiny.rf_association().equals(tiny.rf_association(until=None))  # bulk path unchanged


def test_features_many_matches_features(p1_index) -> None:
    with DuckTrackStore(p1_index.cfg.app.paths.duckdb, p1_index.cfg.app) as st:
        ids = sorted(st.tracks_before(T0 + timedelta(days=400)).track_id)[:3]
        many = st.features_many(list(reversed(ids)))
        one = pd.concat([st.features(t) for t in ids], ignore_index=True)
        assert many.equals(one)
        assert len(st.features_many([])) == 0
