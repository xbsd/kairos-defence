"""SPEC §16.1, D-105: the live loop on the P1 nights' live incident, with the hand-set models."""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import pytest

from kairos_defense.live.loop import TOP_N, rerun_seconds
from kairos_defense.live.replay import load_incident
from tests.conftest import make_loop


def _strip(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in ("elapsed_ms", "timings", "cached")}


def test_rerun_seconds_schedule() -> None:
    assert rerun_seconds(62, 45, 5) == [45, 50, 55, 60]
    assert rerun_seconds(44, 45, 5) == []
    assert rerun_seconds(515, 45, 5)[-1] == 515 and len(rerun_seconds(515, 45, 5)) == 95


def test_result_snaps_to_latest_rerun_second(live_loop) -> None:
    assert live_loop.rerun_at(93) == 90 and live_loop.rerun_at(90) == 90
    assert live_loop.rerun_at(44.9) is None
    assert live_loop.result_at(93)["t_s"] == 90


def test_no_result_before_min_track_s(live_loop) -> None:
    assert live_loop.result_at(30) is None and live_loop.waiting_for_s(30) == 15


def test_same_second_identical_results(live_kit, live_loop) -> None:
    a = live_loop.compute(90)
    b = make_loop(live_kit).compute(90)
    assert json.dumps(_strip(a), sort_keys=True) == json.dumps(_strip(b), sort_keys=True)
    assert a["elapsed_ms"] > 0 and a["cached"] is False


def test_matches_started_before_live_start(live_loop, live_kit) -> None:
    res = live_loop.result_at(90)
    assert res["matches"] and len(res["matches"]) <= TOP_N
    start = live_kit.incident.start_ts
    for m in res["matches"]:
        assert datetime.fromisoformat(m["start_ts"].removesuffix("Z")) < start  # rule 3
        assert m["incident_id"] != live_kit.incident.incident_id
    assert [m["rank"] for m in res["matches"]] == list(range(1, len(res["matches"]) + 1))
    assert all(len(m["local_start"]) == 16 for m in res["matches"])


def test_features_at_ignores_later_points(live_kit) -> None:
    inc = live_kit.incident
    loop = make_loop(live_kit)
    before = loop.features_at(60)
    extra = inc.points.iloc[[-1]].copy()
    extra["t_s"] = 61.0
    extra["ts"] = inc.start_ts + pd.Timedelta(seconds=61)
    extra["x_m"] += 5000.0
    other = load_incident(live_kit.store, inc.incident_id)
    pts = pd.concat([other.points, extra]).sort_values("ts").reset_index(drop=True)
    object.__setattr__(other, "points", pts)
    after = make_loop(live_kit, incident=other).features_at(60)
    assert after == before
    assert set(before) >= {"t_s", "speed_ms", "alt_m", "turn_rate_dps", "dist_target_m",
                           "vspeed_ms", "phase", "track_id", "target_asset_id"}  # fmt: skip
    assert before["phase"] in ("approach", "loiter", "egress")


def test_result_has_forecast_recall_and_lens_for_top_match(live_loop) -> None:
    res = live_loop.result_at(105)
    top = res["matches"][0]
    assert res["dtw"]["match_track_id"] == top["track_id"]
    assert res["dtw"]["channel"] == "dist_target_m" and res["dtw"]["shape"][0] >= 2
    assert res["recall"] is not None and len(res["recall"]["matches"]) <= 3
    for mr in res["recall"]["matches"]:
        for rep in mr["reports"]:
            assert rep["event_ts"].endswith("Z") and "clues" in rep
    if res["forecast"] is not None:
        f = res["forecast"]
        assert f["radius_m"] > 0 and len(f["path"]) > 2 and isinstance(f["roads"], list)
    json.dumps(res, allow_nan=False)  # NaN-free


def test_lens_for_another_match_and_channel(live_loop) -> None:
    res = live_loop.result_at(90)
    second = res["matches"][1]["track_id"]
    lens = live_loop.lens(90, second, "speed_ms")
    assert lens["match_track_id"] == second and lens["channel"] == "speed_ms"
    assert live_loop.lens(90, res["matches"][0]["track_id"]) == res["dtw"]
    with pytest.raises(KeyError):
        live_loop.lens(90, "NOT-A-TRACK")
    with pytest.raises(KeyError):
        live_loop.lens(10, second)


def test_swarm_incident_has_no_single_track_result(live_kit) -> None:
    inc = live_kit.incident
    swarm = type(inc)(**{**inc.__dict__, "is_swarm": True})
    loop = make_loop(live_kit, incident=swarm)
    assert not loop.matching and loop.result_at(90) is None and loop.features_at(90) is None
