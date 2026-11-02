"""Learning closed live incidents (D-176) and no look-ahead (rule 3) in live mode."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.build import track_rows
from kairos_defense.features.signatures import SensorContext
from kairos_defense.match.candidates import FAR_FUTURE
from kairos_defense.match.query import load_query, query_at
from kairos_defense.sim import live_scenarios as ls
from kairos_defense.sim.live_clock import LiveClock
from tests.unit.live_kit import feed, rows


@pytest.fixture(scope="module")
def learned(live_services, world, tmp_path_factory):
    live = live_services.live
    clock = LiveClock(tmp_path_factory.mktemp("clk") / "clock.json",
                      live_services.cfg.world.calendar.end_local)  # fmt: skip
    sc = ls.build(live_services.cfg, world, clock, "returning-prober", seed=7, base="BRAVO")
    half = [m for ms, m in sc.detections() if ms <= sc.start_ms + 200_000]
    live.hub.ingest(rows(half))
    open_state = {
        "signatures": live.store.tracks_before(FAR_FUTURE)["track_id"].tolist(),
        "has_vectors": live.vectors.has("flight_windows"),
        "incident": live.feed.incidents().iloc[0]["state"],
    }
    feed(live.hub, sc, frame_s=50.0)
    clock.reserve(ls.reserve_until(sc, live_services.cfg))
    later = ls.build(live_services.cfg, world, clock, "returning-prober", seed=8, base="BRAVO")
    inc = live.feed.incidents().iloc[0]
    return {"sc": sc, "later": later, "open": open_state, "incident": inc["incident_id"],
            "track": inc["incident_id"] + "-T1"}  # fmt: skip


def test_an_open_incident_is_never_a_candidate(learned) -> None:
    o = learned["open"]
    assert o["incident"] == "open"
    assert not any(t.startswith("LIVE-") for t in o["signatures"])
    assert not o["has_vectors"]


def test_learned_rows_equal_what_the_index_build_writes(learned, live_services) -> None:
    live, tid = live_services.live, learned["track"]
    pts = live.feed.track_points(tid)
    site = live.hub.sites["BRAVO"]
    ctx = SensorContext(**live.feed.sensor_context_until(tid, FAR_FUTURE))
    want = track_rows(tid, learned["incident"], pts, site, ctx, live_services.cfg.scoring)
    got = live.feed.features(tid)
    pd.testing.assert_frame_equal(got.reset_index(drop=True), want.features.reset_index(drop=True),
                                  check_dtype=False)  # fmt: skip
    sig = live.feed.signature(tid)
    for k, v in want.signature.items():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            assert sig[k] is None or pd.isna(sig[k]), k
        elif k in ("start_ts", "end_ts"):
            assert pd.Timestamp(sig[k]) == pd.Timestamp(v), k
        else:
            assert (sig[k] == pytest.approx(v)) if isinstance(v, float) else (sig[k] == v), k
    n = live.vectors.count("flight_windows", f"track_id = '{tid}'")
    assert n == len(want.windows) > 0


def test_a_later_live_flight_can_match_the_learned_one(learned, live_services) -> None:
    live, later = live_services.live, learned["later"]
    pts = pd.DataFrame([{"track_id": "LIVE-Q-T1", "ts": pd.Timestamp(m["ts"]).tz_localize(None),
                         "x_m": m["x_m"], "y_m": m["y_m"], "alt_m": m["alt_m"],
                         "quality": m["quality"]}
                        for _, m in later.detections() if m["type"] == "point"])  # fmt: skip
    q = query_at(pts, live.hub.sites["BRAVO"], 150, live_services.cfg.scoring,
                 {"track_id": "LIVE-Q-T1", "incident_id": "LIVE-Q"})  # fmt: skip
    with live_services.lock:
        res = live.matcher.match(q)
    ids = [m.track_id for m in res.matches]
    assert learned["track"] in ids  # learned live history is searchable
    assert all(m.start_ts < q.start_ts for m in res.matches)  # rule 3


def test_an_earlier_query_never_sees_the_learned_flight(learned, live_services) -> None:
    live = live_services.live
    q = load_query(live.store, "P1-DELTA-260419-T1", 120, live_services.cfg.scoring)
    with live_services.lock:
        res = live.matcher.match(q)
    assert res.matches and not any(m.track_id.startswith("LIVE-") for m in res.matches)
    assert all(m.start_ts < q.start_ts for m in res.matches)
