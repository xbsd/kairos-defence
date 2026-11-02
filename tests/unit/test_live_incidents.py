"""Live incident formation and closing (D-174): single track, swarm, idle close, ids."""

from __future__ import annotations

from kairos_defense.live.incidents import IncidentTracker

T0 = 1_788_400_000_000  # 2026-09-03T01:46:40Z


def tracker(cfg) -> IncidentTracker:
    return IncidentTracker(cfg.scoring, {"BRAVO": ("COASTAL", -5), "ALPHA": ("COASTAL", -5)})


def test_one_track_opens_one_incident_at_its_first_point(cfg) -> None:
    t = tracker(cfg)
    trk, ev = t.point("BRAVO", "TRK-A", T0, 0.0, 0.0)
    assert [e for e, _ in ev] == ["opened"]
    inc = ev[0][1]
    assert inc.incident_id == "LIVE-BRAVO-260902-204640"  # local (UTC-5) time of the first point
    assert trk.track_id == inc.incident_id + "-T1" and inc.start_ms == T0
    for k in range(1, 60):
        _, ev = t.point("BRAVO", "TRK-A", T0 + k * 1000, k * 5.0, 0.0)
        assert ev == []
    assert inc.tracks == [trk.track_id] and not inc.is_swarm and inc.t_s(T0 + 2500) == 2.5


def test_idle_close_on_feed_time(cfg) -> None:
    t = tracker(cfg)
    t.point("BRAVO", "TRK-A", T0, 0.0, 0.0)
    last = T0 + 100_000
    t.point("BRAVO", "TRK-A", last, 10.0, 0.0)
    assert t.idle("BRAVO", last + 30_000) == []  # exactly idle_close_s: still open
    assert t.idle("ALPHA", last + 99_000) == []  # another installation's feed time
    (inc,) = t.idle("BRAVO", last + 30_001)
    assert inc.state == "closing" and t.open_incidents() == []
    assert t.idle("BRAVO", last + 90_000) == []  # once


def test_rf_heard_at_the_installation_keeps_an_incident_open_through_a_radar_gap(cfg) -> None:
    t = tracker(cfg)
    t.point("BRAVO", "TRK-A", T0, 0.0, 0.0)
    assert t.idle("BRAVO", T0 + 45_000, heard_ms=T0 + 20_000) == []  # RF 20 s in: still active
    t.point("BRAVO", "TRK-A", T0 + 46_000, 5.0, 0.0)  # the radar reacquires: same track
    assert len(t.incidents) == 1 and len(t.tracks) == 1
    (inc,) = t.idle("BRAVO", T0 + 46_000 + 30_001, heard_ms=T0 + 40_000)
    assert inc.state == "closing"


def test_nearby_concurrent_tracks_form_one_swarm_incident(cfg) -> None:
    t = tracker(cfg)
    ids = set()
    for d in range(5):
        trk, _ = t.point("BRAVO", f"TRK-{d}", T0 + d * 400, 40.0 * d, 0.0)
        ids.add(trk.incident_id)
    (iid,) = ids
    inc = t.incidents[iid]
    assert len(inc.tracks) == 5 and inc.is_swarm and inc.tracks[4].endswith("-T5")


def test_two_tracks_are_not_a_swarm(cfg) -> None:
    t = tracker(cfg)
    t.point("BRAVO", "TRK-0", T0, 0.0, 0.0)
    trk, ev = t.point("BRAVO", "TRK-1", T0 + 500, 50.0, 0.0)
    assert [e for e, _ in ev] == ["joined"] and not t.incidents[trk.incident_id].is_swarm


def test_distant_or_late_tracks_open_their_own_incident(cfg) -> None:
    t = tracker(cfg)
    a, _ = t.point("BRAVO", "TRK-0", T0, 0.0, 0.0)
    far, ev = t.point("BRAVO", "TRK-1", T0 + 1000, 2000.0, 0.0)  # beyond max_spacing_m
    assert [e for e, _ in ev] == ["opened"] and far.incident_id != a.incident_id
    late, ev = t.point("BRAVO", "TRK-2", T0 + 20_000, 10.0, 0.0)  # beyond join_window_s
    assert [e for e, _ in ev] == ["opened"] and late.incident_id not in {
        a.incident_id,
        far.incident_id,
    }
    other, _ = t.point("ALPHA", "TRK-3", T0 + 1000, 0.0, 0.0)  # another installation
    assert other.incident_id.startswith("LIVE-ALPHA-")


def test_a_track_after_close_opens_a_new_incident(cfg) -> None:
    t = tracker(cfg)
    a, _ = t.point("BRAVO", "TRK-A", T0, 0.0, 0.0)
    t.idle("BRAVO", T0 + 40_000)
    b, ev = t.point("BRAVO", "TRK-A", T0 + 41_000, 0.0, 0.0)  # the same sensor id again
    assert [e for e, _ in ev] == ["opened"]
    assert b.incident_id != a.incident_id and b.track_id != a.track_id


def test_ids_never_clash(cfg) -> None:
    t = IncidentTracker(cfg.scoring, {"BRAVO": ("COASTAL", -5)}, used=["LIVE-BRAVO-260902-204640"])
    trk, _ = t.point("BRAVO", "TRK-A", T0, 0.0, 0.0)
    assert trk.incident_id == "LIVE-BRAVO-260902-204640-2"


def test_reruns_from_min_track_s_every_rerun_every_s(cfg) -> None:
    t = tracker(cfg)
    _, ev = t.point("BRAVO", "TRK-A", T0, 0.0, 0.0)
    inc = ev[0][1]
    assert t.due_reruns(inc, T0 + 44_999) == []
    assert t.due_reruns(inc, T0 + 45_000) == [45.0]
    assert t.due_reruns(inc, T0 + 62_000) == [50.0, 55.0, 60.0]
    assert t.due_reruns(inc, T0 + 62_000) == []
    t.idle("BRAVO", T0 + 100_000)
    assert t.due_reruns(inc, T0 + 200_000) == []  # closing: no more reruns


def test_forget_keeps_used_ids(cfg) -> None:
    t = tracker(cfg)
    a, _ = t.point("BRAVO", "TRK-A", T0, 0.0, 0.0)
    t.forget()
    assert t.incidents == {} and t.tracks == {}
    b, _ = t.point("BRAVO", "TRK-A", T0, 0.0, 0.0)
    assert b.incident_id == a.incident_id + "-2"
