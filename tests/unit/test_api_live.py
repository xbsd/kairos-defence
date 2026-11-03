"""Live mode's API (D-170, D-173, D-182 to D-184) over the P1 nights with the hand-set models."""

from __future__ import annotations

import logging
import shutil
import sys
import time

import pytest
from pydantic import TypeAdapter

from kairos_defense.api.schemas import MatcherTraceMsg
from kairos_defense.api.schemas_live import LiveStreamMessage
from kairos_defense.sim import live_scenarios as ls
from kairos_defense.sim import writers
from kairos_defense.sim.live_clock import LiveClock
from tests.conftest import api_config
from tests.unit.live_kit import fast_scoring

LIVE = TypeAdapter(LiveStreamMessage)
STUB = [sys.executable, "-c", "import time; time.sleep(1.5)"]


@pytest.fixture(scope="module")
def lclient(toy_models, seeded_p1, tmp_path_factory, monkeypatch_module):
    """A TestClient with live mode (worker on submit), a stub simulator and a scratch copy of
    the truth file (the reveal tests write live flights into it)."""
    from fastapi.testclient import TestClient

    from kairos_defense.api.app import create_app

    folder = tmp_path_factory.mktemp("api_live")
    c = api_config(fast_scoring(toy_models), seeded_p1.path, folder)
    truth = folder / "gt.duckdb"
    shutil.copyfile(toy_models.app.paths.truth, truth)
    c = c.model_copy(update={"app": c.app.model_copy(update={
        "paths": c.app.paths.model_copy(update={"truth": truth})})})  # fmt: skip
    monkeypatch_module.setenv("KD_VALIDATE_STREAM", "1")
    app = create_app(c, live_threaded=False, sim_command=lambda a: STUB)
    with TestClient(app) as client:
        client.cfg = c
        yield client


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def flight(lclient, world, tmp_path_factory):
    clock = LiveClock(tmp_path_factory.mktemp("clk") / "clock.json",
                      lclient.cfg.world.calendar.end_local)  # fmt: skip
    return ls.build(lclient.cfg, world, clock, "returning-prober", seed=7, base="BRAVO")


def frames(sc, frame_s=50.0):
    det = sc.detections()
    end = det[-1][0] + 32_000
    t, i = sc.start_ms, 0
    while t < end:
        t = min(t + round(frame_s * 1000), end)
        j = i
        while j < len(det) and det[j][0] <= t:
            j += 1
        yield [m for _, m in det[i:j]] + [
            {"v": 1, "type": "heartbeat", "installation_id": "BRAVO", "ts": ls.iso_ms(t)}
        ]
        i = j


def test_status_and_scenarios(lclient) -> None:
    st = lclient.get("/api/live/status").json()
    assert st["enabled"] and st["matching"] and st["incidents"] == [] and st["pending"] == 0
    assert st["simulator"]["running"] is False
    names = [s["name"] for s in lclient.get("/api/live/scenarios").json()]
    assert names == list(ls.SCENARIOS)


def test_rest_ingest_acks_accepted_and_rejected(lclient) -> None:
    good = {"v": 1, "type": "heartbeat", "installation_id": "BRAVO", "ts": "2026-09-02T01:00:00Z"}
    r = lclient.post(
        "/api/ingest",
        json={"messages": [good, {"type": "sonar"}, {**good, "installation_id": "ZULU"}]},
    )
    ack = r.json()
    assert r.status_code == 200 and ack["accepted"] == 1 and ack["detections"] == 0
    assert [x["index"] for x in ack["rejected"]] == [1, 2]
    assert "unknown installation" in ack["rejected"][1]["reason"]


def test_ws_ingest_acks_each_frame(lclient) -> None:
    beat = {"v": 1, "type": "heartbeat", "installation_id": "ALPHA", "ts": "2026-09-02T01:00:00Z"}
    with lclient.websocket_connect("/ws/ingest") as ws:
        ws.send_json([beat, beat])
        assert ws.receive_json() == {"type": "ack", "accepted": 2, "detections": 0,
                                     "rejected": []}  # fmt: skip
        ws.send_text("not json")
        assert ws.receive_json()["rejected"][0]["reason"] == "not JSON"


def test_reveal_404_unknown(lclient) -> None:
    assert lclient.get("/api/live/incidents/LIVE-NOPE/reveal").status_code == 404


def test_live_stream_from_open_to_close_and_reveal(lclient, flight) -> None:
    writers.record_live_flights(lclient.cfg.app, flight.truth_rows())
    got = []
    with lclient.websocket_connect("/ws/live/BRAVO") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["installation_id"] == "BRAVO"
        fs = list(frames(flight))
        for k, frame in enumerate(fs):
            ack = lclient.post("/api/ingest", json={"messages": frame}).json()
            assert ack["rejected"] == []
            if k == 1:  # the incident is open now: who flew it is not revealed
                st = lclient.get("/api/live/status").json()
                (row,) = st["incidents"]
                assert row["state"] == "open"
                r = lclient.get(f"/api/live/incidents/{row['incident_id']}/reveal")
                assert r.status_code == 409
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            m = ws.receive_json()
            LIVE.validate_python(m)
            got.append(m)
            if m["type"] == "incident_closed":
                break
    kinds = {m["type"] for m in got}
    assert {"incident_opened", "point", "match", "ingest", "incident_closed"} <= kinds
    iid = got[-1]["incident_id"]
    doc = lclient.get(f"/api/live/incidents/{iid}/reveal").json()
    assert doc["actor_id"] == "P1" and doc["nickname"] == "County Rd operator"
    assert doc["scenario"] == "returning-prober" and doc["seed"] == 7 and doc["known"]
    assert doc["reruns"] and doc["words"].startswith("P1, County Rd operator.")
    assert doc["expectation"]["met"] in (True, False)
    # nothing revealed is stored: the live-mode tables and the ledger never name the actor
    live = lclient.app.state.services.live
    for t in ("live_incidents", "live_tracks", "live_results"):
        text = live.feed.sql(f"SELECT * FROM {t}").to_json(date_format="iso")
        assert "County Rd" not in text and '"P1"' not in text
    hist = lclient.get(f"/api/history/{iid}-T1?frame=target")
    assert hist.status_code == 200 and hist.json()["points"]  # learned: a ghost trail too
    # the latest live rerun's matcher trace (D-188): the one streamed with the last match
    r = lclient.get("/api/live/trace", params={"installation": "BRAVO"})
    assert r.status_code == 200
    tr = MatcherTraceMsg.model_validate(r.json())
    last = [m for m in got if m["type"] == "match"][-1]
    assert tr.incident_id == iid and tr.t_s == last["t_s"]
    top3 = [m["track_id"] for m in last["matches"][:3]]
    assert [x.track_id for x in tr.trace.ranking[:3]] == top3
    streamed = [m for m in got if m["type"] == "matcher_trace"]
    assert streamed and streamed[-1]["t_s"] == tr.t_s


def test_launch_one_at_a_time_and_validation(lclient) -> None:
    r = lclient.post("/api/sim/launch", json={"scenario": "returning-prober", "speed": 5})
    assert r.status_code == 200
    doc = r.json()
    assert doc["base"] == "BRAVO" and 1 <= doc["seed"] < 2**31 and doc["pid"] > 0
    assert lclient.post("/api/sim/launch", json={"scenario": "hobbyist"}).status_code == 409
    st = lclient.get("/api/live/status").json()["simulator"]
    assert st["running"] and st["scenario"] == "returning-prober" and "actor" not in st
    assert lclient.app.state.services.live.launcher.wait(10) == 0
    for body in ({"scenario": "nope"}, {"scenario": "returning-prober", "actor": "P9"},
                 {"scenario": "returning-prober", "speed": 99},
                 {"scenario": "copycat", "actor": "random"}):  # fmt: skip
        assert lclient.post("/api/sim/launch", json=body).status_code == 422, body


def test_a_launched_child_log_never_names_the_actor(lclient, caplog) -> None:
    from kairos_defense.api.launcher import SimLauncher

    launcher = lclient.app.state.services.live.launcher
    real = SimLauncher(launcher.folder, lclient.cfg.root / "config")
    launcher.command = lambda a: [*real._command(a), "--dry-run"]
    try:
        with caplog.at_level(logging.DEBUG):
            for args in (
                {"actor": "P3", "base": "ECHO"},  # a valid flight
                {"actor": "P3", "base": "BRAVO"},
            ):  # refused by the child itself
                launcher.launch({"scenario": "returning-prober", "speed": 1, "seed": 5,
                                 "url": "ws://127.0.0.1:9/ws/ingest", **args})  # fmt: skip
                launcher.wait(60)
    finally:
        launcher.command = lambda a: STUB
    logs = sorted((launcher.folder / "sim").glob("*.log"))
    text = "".join(p.read_text() for p in logs[-2:])
    assert "seed 5" in text and "scenario refused" in text
    for word in ("P3", "Munitions figure-eight"):
        assert word not in text
    assert "--actor" not in caplog.text and "P3" not in caplog.text


def test_reset_through_the_api(lclient) -> None:
    r = lclient.post("/api/live/reset").json()
    assert set(r) == {"reset", "vectors", "stopped_simulator"}
    assert lclient.get("/api/live/status").json()["incidents"] == []
