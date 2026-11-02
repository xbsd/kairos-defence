"""The live hub end to end on the P1 nights (D-174 to D-176, D-181): a simulated prober is fed,
incidented, rerun on what was received, proposed, closed and learned. The feed is played in
frames of feed time and the worker runs on submit, so nothing waits in real time."""

from __future__ import annotations

import pandas as pd
import pytest

from kairos_defense.sim import live_scenarios as ls
from kairos_defense.sim.live_clock import LiveClock
from tests.unit.live_kit import feed


@pytest.fixture(scope="module")
def played(live_services, world, tmp_path_factory):
    """One P1 flight at BRAVO fed in 1 s frames; what the stream and the worker saw."""
    svc, live = live_services, live_services.live
    clock = LiveClock(tmp_path_factory.mktemp("clk") / "clock.json",
                      svc.cfg.world.calendar.end_local)  # fmt: skip
    sc = ls.build(svc.cfg, world, clock, "returning-prober", seed=7, base="BRAVO")
    sub = live.hub.subscribe("BRAVO")
    seen = []
    orig = live.compute.rerun

    def spy(task):
        seen.append((task.t_s, task.meta["start_ts"], task.points["ts"].max(), len(task.points)))
        return orig(task)

    live.compute.rerun = spy
    acks = feed(live.hub, sc, frame_s=1.0)
    live.compute.rerun = orig
    msgs = sub.drain()
    sub.close()
    (inc,) = live.feed.incidents().to_dict("records")
    return {"sc": sc, "acks": acks, "msgs": msgs, "inc": inc, "seen": seen, "clock": clock}


def test_every_detection_is_accepted(played) -> None:
    acks = played["acks"]
    assert sum(len(a["rejected"]) for a in acks) == 0
    assert sum(a["detections"] for a in acks) == len(played["sc"].detections())


def test_one_incident_opens_and_closes_with_learned_history(played, live_services) -> None:
    inc, live = played["inc"], live_services.live
    assert inc["incident_id"].startswith("LIVE-BRAVO-260901-21") and inc["state"] == "closed"
    assert inc["n_tracks"] == 1 and not inc["is_swarm"]
    kinds = [m["type"] for m in played["msgs"]]
    assert kinds.index("incident_opened") < kinds.index("hello") < kinds.index("point")
    assert kinds[-1] == "incident_closed"
    for k in ("rf", "ingest", "features", "match", "forecast", "dtw"):
        assert k in kinds, k
    closed = played["msgs"][-1]
    assert closed["learned_tracks"] == 1 and closed["reruns"] == len(played["seen"])
    tid = inc["incident_id"] + "-T1"
    assert live.feed.signature(tid)["incident_id"] == inc["incident_id"]
    assert live.vectors.count("flight_windows", f"track_id = '{tid}'") > 0


def test_reruns_use_only_the_points_received_by_then(played) -> None:
    seen = played["seen"]
    assert [t for t, *_ in seen[:3]] == [45.0, 65.0, 85.0]  # min_track_s, then every 20 s
    for t, start, last, _ in seen:
        assert pd.Timestamp(last) <= pd.Timestamp(start) + pd.Timedelta(seconds=t)  # rule 3
    counts = [n for *_, n in seen]
    assert counts == sorted(counts) and len(set(counts)) == len(counts)  # no empty repeats


def test_results_are_recorded_and_streamed(played, live_services) -> None:
    res = live_services.live.feed.results(played["inc"]["incident_id"])
    assert [r["t_s"] for r in res] == [round(t) for t, *_ in played["seen"]]
    assert all(r["kind"] == "track" and r["matches"] for r in res)
    top = res[-1]["matches"][0]
    assert top["incident_id"].startswith("P1-") or top["incident_id"].startswith("DEMO")
    matches = [m for m in played["msgs"] if m["type"] == "match"]
    assert [m["t_s"] for m in matches] == [float(r["t_s"]) for r in res]
    assert all(m["query_track"].endswith("-T1") for m in matches)


def test_proposals_land_in_the_ledger_once(played, live_services) -> None:
    iid = played["inc"]["incident_id"]
    rows = live_services.memory.events()
    rec = [r for r in rows if r["event_type"] == "incident_recorded" and r["subject_id"] == iid]
    props = [r for r in rows if r["event_type"] == "match_proposed"
             and r["object_json"]["query_incident"] == iid]  # fmt: skip
    assert len(rec) == 1 and props  # P1's past flights belong to the seeded P1 case
    batches = {(r["recorded_at"], tuple(r["object_json"]["top3"])) for r in props}
    assert len(batches) * 3 == len(props) <= 3 * len(played["seen"])
    assert live_services.memory.verify_chain() is None


def test_the_feed_speed_does_not_change_the_results(played, live_services) -> None:
    live = live_services.live
    first = {r["t_s"]: r["matches"] for r in live.feed.results(played["inc"]["incident_id"])}
    live.reset()
    feed(live.hub, played["sc"], frame_s=50.0)  # the same flight, 50 s of feed time per frame
    (inc,) = live.feed.incidents().to_dict("records")
    again = {r["t_s"]: r["matches"] for r in live.feed.results(inc["incident_id"])}
    assert again == first


def test_relaunching_the_seed_later_opens_a_new_incident(played, live_services, world) -> None:
    live, clock = live_services.live, played["clock"]
    clock.reserve(ls.reserve_until(played["sc"], live_services.cfg))
    sc = ls.build(live_services.cfg, world, clock, "returning-prober", seed=7, base="BRAVO")
    assert sc.start_ms > played["sc"].end_ms
    before = set(live.feed.incidents()["incident_id"])
    feed(live.hub, sc, frame_s=25.0)
    new = live.feed.incidents()
    new = new[~new["incident_id"].isin(before)]
    assert len(new) == 1 and new.iloc[0]["state"] == "closed"
    ids = set(live.feed.live_tracks()["sensor_track_id"])
    assert len(ids) == len(live.feed.live_tracks())  # every launch has its own sensor track ids


def test_flush_closes_an_incident_whose_feed_went_silent(live_services, world, tmp_path) -> None:
    from tests.unit.live_kit import rows

    live = live_services.live
    live.reset()
    clock = LiveClock(tmp_path / "c.json", live_services.cfg.world.calendar.end_local)
    clock.reserve(clock.next_ms(-5) + 3 * 86_400_000)
    sc = ls.build(live_services.cfg, world, clock, "returning-prober", seed=9, base="BRAVO")
    det = [m for ms, m in sc.detections() if ms <= sc.start_ms + 300_000]
    live.hub.ingest(rows(det))
    (inc,) = live.feed.incidents().to_dict("records")
    assert inc["state"] == "open"
    assert live.hub.flush(["BRAVO"]) == 1
    assert live.feed.incident(inc["incident_id"])["state"] == "closed"


def test_the_hub_refuses_what_only_the_app_can_check(live_services) -> None:
    from tests.unit.live_kit import rows

    hub = live_services.live.hub
    ok = {"v": 1, "type": "point", "installation_id": "BRAVO", "sensor_id": "BRAVO-RADAR-1",
          "sensor_track_id": "TRK-X", "ts": "2026-09-10T02:00:00Z", "x_m": 0.0, "y_m": 0.0,
          "alt_m": 50.0, "quality": 0.9}  # fmt: skip
    bad = [
        {**ok, "installation_id": "ZULU"},
        {**ok, "sensor_id": "BRAVO-RF-1"},
        {**ok, "sensor_id": "ALPHA-RADAR-1"},
        {**ok, "ts": "2026-08-28T02:00:00Z"},
    ]
    res = hub.ingest(rows(bad))
    reasons = [r["reason"] for r in res["rejected"]]
    assert res["accepted"] == 0 and len(reasons) == 4
    assert "unknown installation" in reasons[0] and "not the radar sensor of BRAVO" in reasons[1]
    assert "not the radar sensor of BRAVO" in reasons[2] and "rule 3" in reasons[3]
    hub.ingest(rows([{"v": 1, "type": "heartbeat", "installation_id": "BRAVO",
                      "ts": "2026-09-10T02:10:00Z"}]))  # fmt: skip
    late = hub.ingest(rows([ok]))  # 10 min behind the feed time
    assert late["rejected"][0]["reason"].startswith("late")
