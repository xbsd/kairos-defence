"""The matcher trace on the streams and routes (D-188): a ``matcher_trace`` with each replay
rerun, ``GET /api/trace/{incident}?at=`` and ``GET /api/live/trace``."""

from __future__ import annotations

import time

import pytest
from pydantic import TypeAdapter

from kairos_defense.api.schemas import MatcherTraceMsg, StreamMessage

INC = "DEMO-BRAVO-0828"
TA = TypeAdapter(StreamMessage)
TRACE = TypeAdapter(MatcherTraceMsg)


@pytest.fixture(autouse=True)
def _validate(monkeypatch):
    monkeypatch.setenv("KD_VALIDATE_STREAM", "1")


def test_the_replay_stream_sends_a_trace_with_each_rerun(api) -> None:
    with api.websocket_connect(f"/ws/replay/{INC}") as ws:
        ws.receive_json()
        ws.send_json({"type": "seek", "t_s": 50})
        out, end = [], time.monotonic() + 30
        while time.monotonic() < end:
            m = ws.receive_json()
            TA.validate_python(m)
            out.append(m)
            if m["type"] == "matcher_trace":
                break
    kinds = [m["type"] for m in out]
    assert kinds.index("match") < kinds.index("matcher_trace")
    match = next(m for m in out if m["type"] == "match")
    tr = out[-1]
    assert tr["t_s"] == match["t_s"] == 50.0 and tr["incident_id"] == INC
    assert tr["trace"]["t_s"] == 50
    assert [r["track_id"] for r in tr["trace"]["ranking"][:3]] == [
        m["track_id"] for m in match["matches"][:3]
    ]


def test_get_trace_of_a_replay_rerun(api) -> None:
    r = api.get(f"/api/trace/{INC}", params={"at": 92})
    assert r.status_code == 200
    doc = TRACE.validate_python(r.json())
    assert doc.t_s == 90.0 and doc.trace.query.at_s == 90  # the latest rerun at or before
    assert doc.trace.prefilter.candidates == len(doc.trace.dtw.distance) > 0
    assert api.get("/api/trace/NOPE", params={"at": 90}).status_code == 404
    assert api.get(f"/api/trace/{INC}", params={"at": 10}).status_code == 422


def test_live_trace_404_before_any_rerun(api) -> None:
    r = api.get("/api/live/trace", params={"installation": "BRAVO"})
    assert r.status_code == 404 and "no live rerun" in r.json()["detail"]
    assert api.get("/api/live/trace", params={"installation": "ZULU"}).status_code == 404
