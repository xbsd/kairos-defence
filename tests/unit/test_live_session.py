"""SPEC §16.1–§16.3, D-105 to D-107: one replay client's session, with a fake clock, a recording
sink and a copy of the seeded P1 ledger (no web server, no waiting)."""

from __future__ import annotations

import itertools
import json
from collections import Counter

import pytest

from kairos_defense.live.broadcast import Broadcaster, PublishingMemory
from kairos_defense.live.session import Session, decorate, target_case
from kairos_defense.ports import IngestStat
from tests.conftest import make_loop

CASE = "CASE-P1-DELTA-260419"
MODEL = {"version": "fusion-v1", "sha256": "ab" * 32, "file": "models/fusion_v1.json"}


class FakeTime:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class FakeSink:
    def __init__(self) -> None:
        self.batches: list[tuple[str, int]] = []
        self.totals: Counter = Counter()

    def append(self, table, rows):
        self.batches.append((table, len(rows)))
        self.totals[table] += len(rows)
        return IngestStat(table, len(rows), self.totals[table], 0.25,
                          f"INSERT INTO {table} … {len(rows)} rows")  # fmt: skip

    def count(self, table):
        return self.totals[table]

    def reset(self):
        return {}


@pytest.fixture
def kit(live_kit, live_loop, ledger_copy):
    bus = Broadcaster()
    mem = PublishingMemory(ledger_copy, bus)
    now, sink = FakeTime(), FakeSink()
    s = Session(live_kit.incident, live_loop, sink=sink, memory=mem, feed=bus.subscribe(),
                model=MODEL, now=now)  # fmt: skip
    return s, now, sink, mem, bus


def run(s: Session, now: FakeTime, wall_s: float, dt: float = 0.1) -> list[dict]:
    out = []
    for _ in range(round(wall_s / dt)):
        now.t += dt
        out += s.step()
    return out


def types(msgs) -> Counter:
    return Counter(m["type"] for m in msgs)


def test_hello_first_and_paused(kit) -> None:
    s = kit[0]
    h = s.hello()
    assert h["type"] == "hello" and h["incident_id"] == "DEMO-BRAVO-0828"
    assert h["installation_id"] == "BRAVO" and h["start_ts"].endswith("Z")
    assert h["playing"] is False and h["speed"] == 1.0 and h["matching"] is True
    assert h["duration_s"] == s.incident.duration_s and h["min_track_s"] == 45.0


def test_clock_at_10_hz_while_playing_and_none_while_paused(kit) -> None:
    s, now = kit[0], kit[1]
    assert types(run(s, now, 2.0))["clock"] == 0  # paused at T+0
    s.handle({"type": "play"})
    clocks = [m for m in run(s, now, 2.0) if m["type"] == "clock"]
    assert 19 <= len(clocks) <= 21 and all(m["playing"] for m in clocks)
    assert clocks[-1]["t_s"] == pytest.approx(2.0, abs=0.11) and clocks[-1]["ts"].endswith("Z")
    s.handle({"type": "pause"})
    assert types(run(s, now, 2.0))["clock"] == 0


def test_points_in_order_then_ingest_with_real_counts(kit) -> None:
    s, now, sink = kit[0], kit[1], kit[2]
    s.handle({"type": "speed", "value": 5})
    s.handle({"type": "play"})
    msgs = run(s, now, 4.0)  # T+0 to T+20
    pts = [m for m in msgs if m["type"] == "point"]
    assert pts and [p["t_s"] for p in pts] == sorted(p["t_s"] for p in pts)
    ingest = [m for m in msgs if m["type"] == "ingest"]
    sent = sum(m["type"] == "point" for m in msgs)
    assert sum(m["rows"] for m in ingest if m["table"] == "live_points") == sent
    assert ingest[-1]["total_rows"] == sink.totals[ingest[-1]["table"]]
    assert all("INSERT INTO live_" in m["statement"] for m in ingest)
    first_point = msgs.index(pts[0])
    assert any(m["type"] == "ingest" for m in msgs[first_point:])
    feats = [m for m in msgs if m["type"] == "features"]
    assert [f["t_s"] for f in feats] == [float(x) for x in range(1, len(feats) + 1)]


def test_seek_forward_writes_skipped_detections_in_one_batch(kit) -> None:
    s, sink = kit[0], kit[2]
    out = s.handle({"type": "seek", "t_s": 40})
    assert out[0]["type"] == "clock" and out[0]["seeked"] is True
    ingest = [m for m in out if m["type"] == "ingest"]
    assert [m["table"] for m in ingest] == sorted({m["table"] for m in ingest})
    n_points = int((s.incident.points["t_s"] <= 40).sum())
    assert sink.batches[0] == ("live_points", n_points)
    assert sum(m["type"] == "point" for m in out) == n_points  # catch-up: last 120 s


def test_seek_back_writes_nothing_and_catches_up_last_120_s(kit) -> None:
    s, sink = kit[0], kit[2]
    s.handle({"type": "seek", "t_s": 200})
    n = len(sink.batches)
    out = s.handle({"type": "seek", "t_s": 150})
    assert len(sink.batches) == n and not any(m["type"] == "ingest" for m in out)
    pts = [m["t_s"] for m in out if m["type"] == "point"]
    assert pts and min(pts) > 30 and max(pts) <= 150
    feats = [m["t_s"] for m in out if m["type"] == "features"]
    assert feats[0] == 31.0 and feats[-1] == 150.0


def test_rerun_second_sends_match_forecast_recall_dtw(kit) -> None:
    s = kit[0]
    out = s.handle({"type": "seek", "t_s": 90})
    t = types(out)
    assert t["match"] == 1 and t["dtw"] == 1 and t["recall"] == 1
    m = next(x for x in out if x["type"] == "match")
    assert m["t_s"] == 90.0 and m["matches"] and m["elapsed_ms"] > 0
    assert m["model_version"] == "fusion-v1" and "cached" in m
    for x in m["matches"]:
        assert {"proposal_seq", "decision", "memory_status", "local_start", "reasons"} <= set(x)


def test_dtw_and_recall_sent_only_when_changed(kit) -> None:
    s, now = kit[0], kit[1]
    s.handle({"type": "seek", "t_s": 88})
    s.handle({"type": "play"})
    msgs = run(s, now, 30.0)  # T+88 to T+118: reruns at 90 … 115
    matches = [m for m in msgs if m["type"] == "match"]
    assert len(matches) == 6
    res = [s.loop.result_at(r) for r in (90, 95, 100, 105, 110, 115)]
    changes = 1 + sum(json.dumps(a["dtw"], sort_keys=True) != json.dumps(b["dtw"], sort_keys=True)
                      for a, b in itertools.pairwise(res))  # fmt: skip
    assert sum(m["type"] == "dtw" for m in msgs) == changes


def test_dtw_request_is_answered(kit) -> None:
    s = kit[0]
    s.handle({"type": "seek", "t_s": 90})
    track = s.loop.result_at(90)["matches"][1]["track_id"]
    out = s.handle({"type": "dtw", "match_track_id": track, "channel": "speed_ms"})
    assert out[0]["type"] == "dtw" and out[0]["match_track_id"] == track
    bad = s.handle({"type": "dtw", "match_track_id": "NOPE", "channel": "speed_ms"})
    assert bad[0]["type"] == "error" and bad[0]["recoverable"] is True


def test_first_rerun_records_incident_registers_model_and_proposes(kit) -> None:
    s, mem = kit[0], kit[3]
    head = mem.head().seq
    out = s.handle({"type": "seek", "t_s": 90})
    led = [m for m in out if m["type"] == "ledger"]
    kinds = [m["event_type"] for m in led]
    match = next(m for m in out if m["type"] == "match")
    assert match["case_id"] == CASE  # DELTA, the planted case's founder, is in the top 3
    assert kinds[:2] == ["incident_recorded", "model_registered"]
    assert kinds[2:] == ["match_proposed"] * 3
    assert [m["seq"] for m in led] == list(range(head + 1, head + 6))
    assert all(m["hash"] and m["prev_hash"] and m["recorded_at"].endswith("Z") for m in led)
    assert led[-1]["actor"] == "matcher@fusion-v1"
    seqs = {x["incident_id"]: x["proposal_seq"] for x in match["matches"][:3]}
    assert sorted(seqs.values()) == [m["seq"] for m in led[2:]]


def test_rerun_again_appends_no_duplicate_proposal(kit) -> None:
    s, mem = kit[0], kit[3]
    s.handle({"type": "seek", "t_s": 90})
    n = mem.count()
    out = s.handle({"type": "seek", "t_s": 92})  # same rerun second
    out += s.handle({"type": "seek", "t_s": 90})
    assert mem.count() == n and not any(m["type"] == "ledger" for m in out)


def test_proposals_target_case_of_best_ranked_member(ledger_copy, live_kit) -> None:
    rows = ledger_copy.events()
    at = live_kit.incident.start_ts
    assert target_case(rows, ["P1-BRAVO-251114", "P1-DELTA-260419", "X"], at) == CASE
    assert target_case(rows, ["P1-DELTA-260419"], at) == CASE


def test_no_case_means_no_proposal_and_null_case_id(ledger_copy, live_kit) -> None:
    rows = ledger_copy.events()
    at = live_kit.incident.start_ts
    assert target_case(rows, ["P1-BRAVO-251114", "P1-ALPHA-260303"], at) is None
    ms = [{"incident_id": "P1-ALPHA-260303", "score": 0.9}]
    out = decorate(ms, rows, None, "DEMO-BRAVO-0828", at, {"ALPHA": -5})
    assert out[0]["proposal_seq"] is None and out[0]["decision"] is None
    assert out[0]["memory_status"] == "Open, unattributed"
    delta = decorate([{"incident_id": "P1-DELTA-260419", "score": 0.9}], rows, CASE,
                     "DEMO-BRAVO-0828", at, {"DELTA": -5})  # fmt: skip
    assert delta[0]["memory_status"] == "Closed as hobbyist on Apr 20"


def test_bad_client_message_is_recoverable_error(kit) -> None:
    s = kit[0]
    for bad in ({"type": "fly"}, ["play"], {"type": "speed", "value": 3},
                {"type": "seek", "t_s": "soon"}, {"type": "seek"}):  # fmt: skip
        out = s.handle(bad)
        assert out[0]["type"] == "error" and out[0]["recoverable"] is True, bad


def test_reset_seeks_zero_paused(kit) -> None:
    s, now = kit[0], kit[1]
    s.handle({"type": "play"})
    run(s, now, 1.0)
    out = s.reset()
    assert out[0]["seeked"] and out[0]["t_s"] == 0 and not out[0]["playing"]


@pytest.mark.parametrize("swarm", [False, True])
def test_stream_rate_under_20_per_second_at_1x(kit, live_kit, swarm) -> None:
    s, now = kit[0], kit[1]
    if swarm:  # a five-track incident streams detections only (swarm matching is phase 9)
        from kairos_defense.live.replay import load_incident

        inc = live_kit.incident
        many = load_incident(live_kit.store, inc.incident_id)
        object.__setattr__(many, "is_swarm", True)
        s = Session(many, make_loop(live_kit, incident=many), sink=FakeSink(), now=now)
    s.handle({"type": "seek", "t_s": 60})
    s.handle({"type": "play"})
    msgs = run(s, now, 60.0)
    assert len(msgs) < 1200, types(msgs)


def test_every_message_validates_against_stream_message(kit) -> None:
    from pydantic import TypeAdapter

    from kairos_defense.api.schemas import StreamMessage

    s, now = kit[0], kit[1]
    ta = TypeAdapter(StreamMessage)
    msgs = [s.hello(), *s.handle({"type": "seek", "t_s": 85})]
    s.handle({"type": "speed", "value": 5})
    s.handle({"type": "play"})
    msgs += run(s, now, 3.0)
    msgs += s.handle({"type": "fly"})
    for m in msgs:
        ta.validate_python(json.loads(json.dumps(m, allow_nan=False)))
    assert {"hello", "clock", "point", "rf", "features", "ingest", "match", "dtw",
            "recall", "error"} <= set(types(msgs))  # fmt: skip
