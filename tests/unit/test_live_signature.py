"""SPEC §10.5 partial live signatures: only what was known at T counts (D-071)."""

from __future__ import annotations

import pandas as pd
import pytest

from kairos_defense.features.channels import load_site
from kairos_defense.match.live_signature import query_signature
from kairos_defense.match.query import load_query, query_at
from kairos_defense.store.duck import DuckTrackStore


@pytest.fixture
def store(p1_index):
    st = DuckTrackStore(p1_index.cfg.app.paths.duckdb, p1_index.cfg.app)
    yield st
    st.close()


EXACT = ("track_id", "incident_id", "installation_id", "target_asset_id", "target_kind",
         "loiter_dir", "tod_minutes", "rf_family", "rid_present", "rid_serial", "start_ts",
         "end_ts")  # fmt: skip


@pytest.mark.parametrize("tid", ["P1-DELTA-260419-T1", "P1-ALPHA-260303-T1"])
def test_full_length_query_signature_matches_the_index(p1_index, store, tid: str) -> None:
    stored = store.signature(tid)
    at = int(stored["duration_s"]) + 30  # the ±30 s RF window then agrees with the index's
    sig = query_signature(store, load_query(store, tid, at, p1_index.cfg.scoring))
    for k in EXACT:
        assert sig[k] == stored[k] or (pd.isna(sig[k]) and pd.isna(stored[k])), k
    assert sig["approach_bearing_deg"] == pytest.approx(stored["approach_bearing_deg"], abs=1.0)
    assert sig["loiter_radius_m"] == pytest.approx(stored["loiter_radius_m"], abs=1.0)
    for k in ("alt_median_m", "dwell_s", "launch_x_rel_m", "launch_y_rel_m"):
        assert sig[k] == pytest.approx(stored[k], abs=1e-6, nan_ok=True), k


class SpyStore:
    """Delegates to the real store and records ``sensor_context_until`` bounds."""

    def __init__(self, inner) -> None:
        self.inner, self.bounds = inner, []

    def sensor_context_until(self, track_id, until):
        self.bounds.append(until)
        return self.inner.sensor_context_until(track_id, until)


def test_query_signature_ignores_everything_after_T(p1_index, store) -> None:
    tid, sc = "DEMO-BRAVO-0828-T1", p1_index.cfg.scoring
    pts = store.track_points(tid)
    site = load_site(store, "BRAVO")
    ids = {"track_id": tid, "incident_id": "DEMO-BRAVO-0828"}
    for at in (60, 90, 120):
        q = query_at(pts, site, at, sc, ids)
        tampered = pts.copy()
        after = tampered.ts > pts.ts.iloc[0] + pd.Timedelta(seconds=at)
        tampered.loc[after, ["x_m", "y_m"]] += 3000.0  # a different future
        tampered.loc[after, "alt_m"] = 5.0  # ... landing somewhere else
        spy = SpyStore(store)
        a = query_signature(spy, q)
        b = query_signature(spy, query_at(tampered, site, at, sc, ids))
        assert a == b
        assert spy.bounds == [q.until, q.until]  # sensors are asked only up to T
        assert q.until == pts.ts.iloc[0] + pd.Timedelta(seconds=at)
        assert a["end_ts"] <= q.until and a["recovery_x_rel_m"] is None  # still flying at T


def test_live_p1_signature_at_t90(p1_index, store) -> None:
    sig = query_signature(store, load_query(store, "DEMO-BRAVO-0828-T1", 90, p1_index.cfg.scoring))
    assert sig["rf_family"] == "FAM-07"
    assert sig["approach_bearing_deg"] == pytest.approx(315.0, abs=15.0)
    assert sig["target_asset_id"] == "BRAVO-fuel_farm"
    early = query_signature(store, load_query(store, "DEMO-BRAVO-0828-T1", 45,
                                              p1_index.cfg.scoring))  # fmt: skip
    assert early["target_kind"] == "fence"  # inbound at T+45: the target is not known yet (D-046)
