"""``kairos-defense index`` on the six P1 nights: planted signatures, live exclusion, LanceDB."""

from __future__ import annotations

import numpy as np
import pytest

from kairos_defense.features.build import WINDOWS_TABLE, build_index
from kairos_defense.features.channels import load_site, track_features
from kairos_defense.features.signatures import signature
from kairos_defense.sim.writers import table_hashes
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore

P1 = ["P1-BRAVO-251114", "P1-ALPHA-260303", "P1-DELTA-260419", "P1-ALPHA-260502",
      "P1-CHARLIE-260710"]  # fmt: skip
LIVE = "DEMO-BRAVO-0828"


@pytest.fixture
def store(p1_index):
    s = DuckTrackStore(p1_index.cfg.app.paths.duckdb, p1_index.cfg.app)
    yield s
    s.close()


@pytest.fixture(scope="module")
def lance(p1_index) -> LanceVectorStore:
    return LanceVectorStore(p1_index.cfg.app.paths.lancedb)


def _check_p1(sig: dict) -> None:
    assert abs(((sig["approach_bearing_deg"] - 315.0 + 180) % 360) - 180) <= 15.0, sig
    assert abs(sig["loiter_radius_m"] - 180.0) <= 25.0, sig
    assert sig["loiter_dir"] == "ccw", sig
    assert sig["rf_family"] == "FAM-07" and not sig["rid_present"]


@pytest.mark.parametrize("incident", P1)
def test_p1_planted_signatures(store, incident: str) -> None:
    sig = store.signature(f"{incident}-T1")
    _check_p1(sig)
    expect = "flight_line" if "CHARLIE" in incident else "fuel_farm"  # target_override
    assert sig["target_kind"] == expect


def test_live_p1_signature_computed_from_points(p1_index, store) -> None:
    """The live track is never stored (D-049); computed from its points it matches P1 too."""
    pts = store.track_points(f"{LIVE}-T1")
    site = load_site(store, "BRAVO")
    f, target = track_features(pts, site, p1_index.cfg.scoring)
    ctx = store.sensor_context([f"{LIVE}-T1"])[f"{LIVE}-T1"]
    sig = signature(f, target, pts.iloc[0], pts.iloc[-1], site, ctx,
                    {"track_id": f"{LIVE}-T1", "incident_id": LIVE})  # fmt: skip
    _check_p1(sig)
    assert sig["target_asset_id"] == "BRAVO-fuel_farm"


def test_live_incidents_are_absent_everywhere(p1_index, store, lance) -> None:
    live = set(store.sql("SELECT incident_id FROM incidents WHERE status = 'live'").incident_id)
    assert LIVE in live
    win = lance.to_pandas(WINDOWS_TABLE, ["incident_id", "track_id"])
    assert not set(win.incident_id) & live
    for table in ("track_features", "track_signatures"):
        got = set(store.sql(f"SELECT DISTINCT incident_id FROM {table}").incident_id)
        assert not got & live, table
    assert p1_index.summary.live_tracks_skipped == 1


@pytest.mark.parametrize("size", [60, 120, 300])
def test_filter_returns_only_the_requested_window_size(lance, size: int) -> None:
    q = np.zeros(80, dtype=np.float32)
    q[0] = 1.0
    hits = lance.search(WINDOWS_TABLE, q, f"window_s = {size}", 500)
    assert len(hits) > 0 and set(hits.window_s) == {size}
    assert list(hits._distance) == sorted(hits._distance)
    assert lance.count(WINDOWS_TABLE, f"window_s = {size}") == p1_index_count(lance, size)


def p1_index_count(lance: LanceVectorStore, size: int) -> int:
    return int((lance.to_pandas(WINDOWS_TABLE, ["window_s"]).window_s == size).sum())


def test_window_metadata_matches_signatures(store, lance) -> None:
    win = lance.to_pandas(WINDOWS_TABLE)
    sig = store.sql("SELECT track_id, start_ts, rf_family, tod_minutes FROM track_signatures")
    sig["start_ms"] = sig.start_ts.astype("datetime64[ms]").astype("int64")
    m = win.merge(sig, on="track_id", validate="many_to_one")
    assert (m.start_ts_ms == m.start_ms).all()
    assert (m.win_ts_ms == m.start_ts_ms + 1000 * m.offset_s).all()
    assert (m.rf_family_x == m.rf_family_y).all() and (m.tod_minutes_x == m.tod_minutes_y).all()
    assert win.window_id.is_unique
    v = np.stack(win.vector.to_numpy())
    assert v.shape[1] == 80 and np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)


def test_features_are_one_hz_per_track(store) -> None:
    f = store.features("P1-DELTA-260419-T1")
    assert f.t_s.tolist() == list(range(len(f)))
    assert (np.diff(f.ts.to_numpy()).astype("timedelta64[s]").astype(int) == 1).all()


def test_rebuild_is_deterministic(p1_index, lance) -> None:
    before = table_hashes(p1_index.cfg.app.paths.duckdb)
    w1 = lance.to_pandas(WINDOWS_TABLE).sort_values("window_id").reset_index(drop=True)
    build_index(p1_index.cfg)
    assert table_hashes(p1_index.cfg.app.paths.duckdb) == before
    w2 = lance.to_pandas(WINDOWS_TABLE).sort_values("window_id").reset_index(drop=True)
    assert w1.drop(columns="vector").equals(w2.drop(columns="vector"))
    assert np.array_equal(np.stack(w1.vector.to_numpy()), np.stack(w2.vector.to_numpy()))
