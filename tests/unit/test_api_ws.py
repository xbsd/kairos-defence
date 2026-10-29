"""SPEC §16.3: the replay WebSocket through FastAPI's TestClient (real time, short runs)."""

from __future__ import annotations

import time

import pytest
from pydantic import TypeAdapter

from kairos_defense.api.schemas import StreamMessage

INC = "DEMO-BRAVO-0828"
CASE = "CASE-P1-DELTA-260419"
TA = TypeAdapter(StreamMessage)


@pytest.fixture(autouse=True)
def _validate(monkeypatch):
    monkeypatch.setenv("KD_VALIDATE_STREAM", "1")


def collect(ws, until, limit_s: float = 8.0) -> list[dict]:
    out, end = [], time.monotonic() + limit_s
    while time.monotonic() < end:
        m = ws.receive_json()
        TA.validate_python(m)
        out.append(m)
        if until(out):
            return out
    raise AssertionError(f"timed out; got {sorted({m['type'] for m in out})}")


def test_ws_hello_then_clock_after_play(api) -> None:
    with api.websocket_connect(f"/ws/replay/{INC}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["incident_id"] == INC and not hello["playing"]
        ws.send_json({"type": "play"})
        msgs = collect(ws, lambda o: sum(m["type"] == "clock" for m in o) >= 5)
        clocks = [m for m in msgs if m["type"] == "clock"]
        assert all(c["playing"] for c in clocks) and clocks[-1]["t_s"] > clocks[0]["t_s"]


def test_ws_seek_44_play_5x_reaches_match_with_valid_messages(api) -> None:
    api.post("/api/admin/reseed")
    with api.websocket_connect(f"/ws/replay/{INC}") as ws:
        ws.receive_json()
        for m in ({"type": "speed", "value": 5}, {"type": "seek", "t_s": 44}, {"type": "play"}):
            ws.send_json(m)
        need = {"match", "forecast", "recall", "dtw", "ingest", "ledger", "point", "rf",
                "features", "clock"}  # fmt: skip
        msgs = collect(ws, lambda o: need <= {m["type"] for m in o} and any(
            m.get("event_type") == "match_proposed" for m in o))  # fmt: skip
    match = next(m for m in msgs if m["type"] == "match")
    assert match["t_s"] == 45.0 and match["matches"] and match["case_id"] == CASE
    kinds = [m["event_type"] for m in msgs if m["type"] == "ledger"]
    assert kinds[:2] == ["incident_recorded", "model_registered"] and "match_proposed" in kinds


def test_ws_unknown_incident_sends_error_and_closes(api) -> None:
    with api.websocket_connect("/ws/replay/NOPE") as ws:
        m = ws.receive_json()
        assert m == {"type": "error", "message": "no live incident NOPE", "recoverable": False}


def test_ws_bad_message_is_recoverable(api) -> None:
    with api.websocket_connect(f"/ws/replay/{INC}") as ws:
        ws.receive_json()
        ws.send_text("not json")
        ws.send_json({"type": "speed", "value": 3})
        errs = collect(ws, lambda o: sum(m["type"] == "error" for m in o) >= 2)
        assert all(m["recoverable"] for m in errs if m["type"] == "error")


def test_ws_rest_approval_is_broadcast_as_ledger(api) -> None:
    api.post("/api/admin/reseed")
    with api.websocket_connect(f"/ws/replay/{INC}") as ws:
        ws.receive_json()
        ws.send_json({"type": "seek", "t_s": 90})
        match = next(m for m in iter(ws.receive_json, None) if m["type"] == "match")
        seq = next(m["proposal_seq"] for m in match["matches"] if m["proposal_seq"])
        r = api.post(f"/api/cases/{CASE}/links", json={"proposal_seq": seq, "decision": "approve"})
        assert r.status_code == 200, r.text
        new = r.json()["block"]["seq"]
        got = collect(ws, lambda o: any(m["type"] == "ledger" and m["seq"] == new for m in o))
        led = next(m for m in got if m["type"] == "ledger" and m["seq"] == new)
        assert led["event_type"] == "link_approved" and led["actor"] == "analyst:demo"
