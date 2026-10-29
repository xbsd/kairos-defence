"""SPEC §16.1 and D-118: the replay engine and a live incident's detections."""

from __future__ import annotations

import json

import pytest

from kairos_defense.live.replay import ReplayEngine, live_incident_ids, load_incident


class FakeTime:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def test_t0_is_incident_start_ts(live_kit) -> None:
    inc = live_kit.incident
    start = live_kit.store.sql("SELECT start_ts FROM incidents WHERE incident_id = $i",
                               {"i": inc.incident_id})["start_ts"].iloc[0]  # fmt: skip
    assert inc.start_ts == start.to_pydatetime()
    assert inc.points["t_s"].min() == 0.0
    assert inc.detections(-1, 0)[0]["t_s"] == 0.0 and inc.detections(-1, 0)[0]["type"] == "point"
    assert inc.duration_s == (inc.end_ts - inc.start_ts).total_seconds()


def test_live_incident_ids_and_unknown(live_kit) -> None:
    assert live_incident_ids(live_kit.store)[0] == "DEMO-BRAVO-0828"
    with pytest.raises(KeyError):
        load_incident(live_kit.store, "P1-DELTA-260419")  # a history incident is not live


def test_clock_advances_by_speed_times_wall(live_kit) -> None:
    now = FakeTime()
    e = ReplayEngine(live_kit.incident, 5.0, now)
    e.play()
    now.t += 2.0
    assert e.elapsed_s == pytest.approx(10.0)
    e.set_speed(1.0)
    now.t += 2.0
    assert e.elapsed_s == pytest.approx(12.0)


def test_pause_freezes_clock(live_kit) -> None:
    now = FakeTime()
    e = ReplayEngine(live_kit.incident, 2.0, now)
    e.play()
    now.t += 3.0
    e.pause()
    now.t += 50.0
    assert e.elapsed_s == pytest.approx(6.0) and not e.playing


def test_seek_clamps_to_duration(live_kit) -> None:
    e = ReplayEngine(live_kit.incident, 1.0, FakeTime())
    assert e.seek(1e9) == live_kit.incident.duration_s
    assert e.seek(-5) == 0.0


def test_reset_returns_to_zero_paused(live_kit) -> None:
    now = FakeTime()
    e = ReplayEngine(live_kit.incident, 1.0, now)
    e.play()
    now.t += 30
    e.reset()
    assert e.elapsed_s == 0.0 and not e.playing


def test_speed_accepts_only_1_2_5(live_kit) -> None:
    e = ReplayEngine(live_kit.incident, 1.0, FakeTime())
    for v in (1, 2, 5):
        e.set_speed(v)
        assert e.speed == float(v)
    with pytest.raises(ValueError, match="1, 2 or 5"):
        e.set_speed(3)
    with pytest.raises(ValueError):
        ReplayEngine(live_kit.incident, 0.5, FakeTime())


def test_visible_points_only_up_to_clock(live_kit) -> None:
    e = ReplayEngine(live_kit.incident, 1.0, FakeTime())
    e.seek(30.5)
    vis = e.visible_points()
    assert len(vis) > 0 and vis["t_s"].max() <= 30.5
    assert len(vis) == int((live_kit.incident.points["t_s"] <= 30.5).sum())


def test_detection_messages_half_open_interval(live_kit) -> None:
    inc = live_kit.incident
    edge = inc.messages[8]["t_s"]  # a second that has a detection
    a = inc.detections(-1, edge)
    b = inc.detections(edge, edge + 10)
    assert all(m["t_s"] <= edge for m in a) and all(edge < m["t_s"] <= edge + 10 for m in b)
    assert any(m["t_s"] == edge for m in a) and not any(m["t_s"] == edge for m in b)
    keys = [(m["t_s"], {"point": 0, "rf": 1, "rid": 2}[m["type"]]) for m in a + b]
    assert keys == sorted(keys)
    rows = inc.rows(-1, edge)
    assert len(rows["live_points"]) == sum(m["type"] == "point" for m in a)
    assert len(rows.get("live_rf", [])) == sum(m["type"] == "rf" for m in a)
    assert "t_s" not in rows["live_points"][0]


def test_same_second_same_messages(live_kit) -> None:
    other = load_incident(live_kit.store, live_kit.incident.incident_id)
    a = json.dumps(live_kit.incident.detections(40, 90), sort_keys=True)
    b = json.dumps(other.detections(40, 90), sort_keys=True)
    assert a == b


def test_rf_and_rid_limited_to_installation_and_window(live_kit) -> None:
    inc = live_kit.incident
    assert (inc.rf["installation_id"] == inc.installation_id).all()
    assert inc.rf["ts"].min() >= inc.start_ts and inc.rf["ts"].max() <= inc.end_ts
    assert len(inc.rid) == 0 or (inc.rid["installation_id"] == inc.installation_id).all()
    assert {m["type"] for m in inc.messages} <= {"point", "rf", "rid"}


def test_replay_pauses_at_duration(live_kit) -> None:
    now = FakeTime()
    e = ReplayEngine(live_kit.incident, 5.0, now)
    e.seek(live_kit.incident.duration_s - 1)
    e.play()
    now.t += 10
    assert e.elapsed_s == live_kit.incident.duration_s and not e.playing
    e.play()  # at the end, play does nothing
    assert not e.playing
