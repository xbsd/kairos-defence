"""SPEC §16.4, D-108: the REST endpoints with FastAPI's TestClient, on the P1 nights."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

INC = "DEMO-BRAVO-0828"
CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"


def _ok(r, code: int = 200):
    assert r.status_code == code, r.text
    return r.json()


@pytest.fixture
def fresh(api):
    """A reseeded ledger and empty live tables."""
    _ok(api.post("/api/admin/reseed"))
    _ok(api.post("/api/admin/reset"))
    return api


def _proposals(api) -> list[dict]:
    """Make the live loop propose at T+90 (through the stream path) and return the matches."""
    with api.websocket_connect(f"/ws/replay/{INC}") as ws:
        ws.receive_json()
        ws.send_json({"type": "seek", "t_s": 90})
        while True:
            m = ws.receive_json()
            if m["type"] == "match":
                return m["matches"]


def test_health(api) -> None:
    h = _ok(api.get("/api/health"))
    assert h["status"] == "ok" and h["matching"] is True and h["problems"] == []
    assert INC in h["live_incidents"] and h["ledger_rows"] > 0


def test_installations_lists_every_base_with_region_and_offset(api) -> None:
    rows = _ok(api.get("/api/installations"))
    ids = {r["installation_id"] for r in rows}
    assert {"ALPHA", "BRAVO", "DELTA"} <= ids
    bravo = next(r for r in rows if r["installation_id"] == "BRAVO")
    assert bravo["region_id"] == "COASTAL" and bravo["utc_offset_hours"] == -5
    assert bravo["name"] == "Installation Bravo"


def test_scene_has_origin_fence_assets_roads_parks_sensors_and_shadow(api) -> None:
    s = _ok(api.get("/api/installations/BRAVO/scene"))
    assert (s["origin_x_m"], s["origin_y_m"]) == (22000.0, -6000.0)
    assert len(s["fence"]) >= 4 and s["fence"][0] == s["fence"][-1]
    assert {a["kind"] for a in s["assets"]} >= {"fuel_farm", "hq"}
    assert {r["name"] for r in s["roads"]} >= {"County Rd 12"}
    assert {x["kind"] for x in s["sensors"]} == {"radar", "rf", "rid"}
    radar = next(x for x in s["sensors"] if x["kind"] == "radar")
    assert radar["rate_hz"] == 1.0 and radar["range_m"] > 0
    sh = s["radar_shadow"]
    assert sh["label"] == "Radar shadow" and sh["bearing_deg"] == [285.0, 20.0] and sh["polygons"]
    assert _ok(api.get("/api/installations/NOPE/scene"), 404)


def test_scene_clips_roads_to_6_km(api) -> None:
    s = _ok(api.get("/api/installations/BRAVO/scene"))
    ox, oy = s["origin_x_m"], s["origin_y_m"]
    for road in s["roads"]:
        for line in road["lines"]:
            assert all(((x - ox) ** 2 + (y - oy) ** 2) ** 0.5 <= s["radius_m"] + 1 for x, y in line)
    assert all(((p["center_x_m"] - ox) ** 2 + (p["center_y_m"] - oy) ** 2) ** 0.5 <= 6000
               for p in s["parks"])  # fmt: skip


def test_incidents_filter_by_status(api) -> None:
    live = _ok(api.get("/api/incidents?status=live"))
    assert [i["incident_id"] for i in live] == [INC] and live[0]["status"] == "live"
    assert live[0]["start_ts"].endswith("Z") and live[0]["duration_s"] > 400
    hist = _ok(api.get("/api/incidents?status=history&limit=3"))
    assert len(hist) == 3 and all(i["status"] == "history" for i in hist)
    assert api.get("/api/incidents?status=all").status_code == 422


def test_match_at_90_snaps_and_returns_10_8_fields(api) -> None:
    d = _ok(api.get(f"/api/match/{INC}?at=93"))
    assert d["t_s"] == 90.0 and d["at"] == 93.0 and d["waiting_for_s"] == 0
    assert d["model_version"] == "fusion-v1" and d["elapsed_ms"] > 0 and d["case_id"] == CASE
    m = d["matches"][0]
    for k in ("query_incident_id", "track_id", "incident_id", "installation_id", "start_ts",
              "score", "shape_sim", "features", "reasons", "warp_ratio", "window_offset_s",
              "model_version", "memory_status", "proposal_seq", "decision"):  # fmt: skip
        assert k in m
    assert next(x for x in d["matches"] if x["incident_id"] == DELTA)["memory_status"] == (
        "Closed as hobbyist on Apr 20")  # fmt: skip
    assert _ok(api.get("/api/match/NOPE?at=90"), 404)


def test_match_before_min_track_is_empty_with_wait(api) -> None:
    d = _ok(api.get(f"/api/match/{INC}?at=30"))
    assert d["matches"] == [] and d["t_s"] is None and d["waiting_for_s"] == 15


def test_dtw_endpoint_equals_stream_payload(api) -> None:
    with api.websocket_connect(f"/ws/replay/{INC}") as ws:
        ws.receive_json()
        ws.send_json({"type": "seek", "t_s": 90})
        msg = next(m for m in iter(ws.receive_json, None) if m["type"] == "dtw")
    rest = _ok(api.get(f"/api/dtw/{INC}/{msg['match_track_id']}?at=90&channel=dist_target_m"))
    assert rest == msg


def test_dtw_unknown_track_404(api) -> None:
    assert api.get(f"/api/dtw/{INC}/NOPE-T1?at=90").status_code == 404
    assert api.get(f"/api/dtw/{INC}/NOPE-T1?at=10").status_code == 404


def test_history_in_target_frame(api) -> None:
    track = _ok(api.get(f"/api/match/{INC}?at=90"))["matches"][0]["track_id"]
    h = _ok(api.get(f"/api/history/{track}?frame=target"))
    assert h["frame"] == "target" and h["columns"] == ["t_s", "x_m", "y_m", "alt_m"]
    assert len(h["points"]) > 100 and h["start_ts"].endswith("Z")
    reg = _ok(api.get(f"/api/history/{track}?frame=region"))
    i = next(i for i, p in enumerate(h["points"]) if p[1] is not None)  # seconds in a gap are null
    assert reg["points"][i][0] == h["points"][i][0] and reg["points"][i][1] != h["points"][i][1]


def test_history_refuses_live_track(api) -> None:
    assert api.get(f"/api/history/{INC}-T1").status_code == 404


def test_case_snapshot_known_then_hobbyist_closed_no_links(api) -> None:
    s = _ok(api.get(f"/api/cases/{CASE}?as_of=2026-04-20T10:00-05:00"))
    assert s["exists"] and s["status"] == "closed" and s["members"] == [DELTA]
    assert s["links"] == [] and [c["value"] for c in s["claims"]] == ["hobbyist"]
    assert api.get("/api/cases/CASE-NOPE").status_code == 404


def test_naive_time_is_422(api) -> None:
    r = api.get(f"/api/cases/{CASE}?as_of=2026-04-20T10:00")
    assert r.status_code == 422 and "Z or an offset" in r.json()["detail"]


def test_link_approve_appends_link_approved(fresh) -> None:
    ms = _proposals(fresh)
    seq = next(m["proposal_seq"] for m in ms if m["incident_id"] != DELTA and m["proposal_seq"])
    d = _ok(fresh.post(f"/api/cases/{CASE}/links",
                       json={"proposal_seq": seq, "decision": "approve", "analyst": "demo",
                             "clock": "2026-08-29T02:41:40Z"}))  # fmt: skip
    b = d["block"]
    assert b["event_type"] == "link_approved" and b["actor"] == "analyst:demo"
    assert b["seq"] == _ok(fresh.get("/api/ledger/verify"))["head_seq"]
    rec = _ok(fresh.get(f"/api/ledger/{b['seq']}"))
    assert rec["object_json"]["proposal_seq"] == seq and rec["hash"] == b["hash"]
    after = _ok(fresh.get(f"/api/match/{INC}?at=90"))["matches"]
    assert next(m for m in after if m["proposal_seq"] == seq)["decision"] == "approved"


def test_link_reject_supersedes_proposal(fresh) -> None:
    ms = _proposals(fresh)
    seq = next(m["proposal_seq"] for m in ms if m["proposal_seq"])
    d = _ok(fresh.post(f"/api/cases/{CASE}/links",
                       json={"proposal_seq": seq, "decision": "reject"}))  # fmt: skip
    rec = _ok(fresh.get(f"/api/ledger/{d['block']['seq']}"))
    assert rec["event_type"] == "link_rejected" and rec["supersedes_seq"] == seq


def test_link_twice_is_409(fresh) -> None:
    seq = next(m["proposal_seq"] for m in _proposals(fresh) if m["proposal_seq"])
    body = {"proposal_seq": seq, "decision": "approve"}
    _ok(fresh.post(f"/api/cases/{CASE}/links", json=body))
    assert fresh.post(f"/api/cases/{CASE}/links", json=body).status_code == 409


def test_link_wrong_case_is_409(fresh) -> None:
    seq = next(m["proposal_seq"] for m in _proposals(fresh) if m["proposal_seq"])
    r = fresh.post("/api/cases/CASE-OTHER/links", json={"proposal_seq": seq, "decision": "approve"})
    assert r.status_code == 409


def test_unknown_proposal_is_404(api) -> None:
    r = api.post(f"/api/cases/{CASE}/links", json={"proposal_seq": 1, "decision": "approve"})
    assert r.status_code == 404  # seq 1 is an incident record, not a proposal
    assert api.post(f"/api/cases/{CASE}/links",
                    json={"proposal_seq": 1, "decision": "maybe"}).status_code == 422  # fmt: skip


def test_evidence_without_approve_is_400_and_writes_nothing(api) -> None:
    n = _ok(api.get("/api/ledger/verify"))["rows"]
    r = api.post(f"/api/cases/{CASE}/evidence", json={"approve": False})
    assert r.status_code == 400 and "rule 8" in r.json()["detail"]
    assert _ok(api.get("/api/ledger/verify"))["rows"] == n
    assert not Path(api.cfg.app.paths.exports).exists()


def test_evidence_streams_file_progress_then_verified_done(fresh) -> None:
    r = fresh.post(f"/api/cases/{CASE}/evidence", json={"approve": True, "analyst": "demo"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    lines = [json.loads(x) for x in r.text.splitlines()]
    files = [x for x in lines if x["type"] == "file"]
    assert [f["name"] for f in files] == ["case.json", "case.html", "pubkey.pem",
                                          "manifest.json", "manifest.sig"]  # fmt: skip
    done = lines[-1]
    assert done["type"] == "done" and done["passed"] and done["signed"]
    assert {c["name"]: c["status"] for c in done["checks"]}["files"] == "PASS"
    assert done["seq"] == _ok(fresh.get("/api/ledger/verify"))["head_seq"]


def test_ledger_verify_intact(api) -> None:
    v = _ok(api.get("/api/ledger/verify"))
    assert v["intact"] and v["first_broken_seq"] is None and v["rows"] == v["head_seq"]


def test_ledger_tail_and_record(api) -> None:
    tail = _ok(api.get("/api/ledger/tail?n=5"))
    assert len(tail) == 5 and [b["seq"] for b in tail] == sorted(b["seq"] for b in tail)
    assert tail[-1]["prev_hash"] == tail[-2]["hash"]
    assert _ok(api.get(f"/api/ledger/{tail[0]['seq']}"))["seq"] == tail[0]["seq"]
    assert api.get("/api/ledger/999999").status_code == 404


def test_admin_reset_empties_live_tables(api) -> None:
    with api.websocket_connect(f"/ws/replay/{INC}") as ws:
        ws.receive_json()
        ws.send_json({"type": "seek", "t_s": 30})
        next(m for m in iter(ws.receive_json, None) if m["type"] == "ingest")
    d = _ok(api.post("/api/admin/reset"))
    assert d["reset"]["live_points"] > 0
    assert _ok(api.post("/api/admin/reset"))["reset"]["live_points"] == 0


def test_admin_reseed_restores_seed_head(api, seeded_p1) -> None:
    _proposals(api)
    d = _ok(api.post("/api/admin/reseed"))
    s = seeded_p1.summary
    assert (d["head_seq"], d["head_hash"]) == (s.head_seq, s.head_hash)
    v = _ok(api.get("/api/ledger/verify"))
    assert v["intact"] and v["head_hash"] == seeded_p1.summary.head_hash


def test_delta_since(api) -> None:
    d = _ok(api.get("/api/delta?since=2026-04-19T00:00Z&until=2026-04-21T00:00Z"))
    assert d["count"] > 0 and "decisions" in d["groups"]
    assert api.get("/api/delta?since=2026-04-19T00:00").status_code == 422


def test_case_diff_lists_added_members(fresh) -> None:
    seq = next(m["proposal_seq"] for m in _proposals(fresh) if m["proposal_seq"]
               and m["incident_id"] != DELTA)  # fmt: skip
    _ok(fresh.post(f"/api/cases/{CASE}/links", json={"proposal_seq": seq, "decision": "approve"}))
    d = _ok(fresh.get(f"/api/cases/{CASE}/diff?t1=2026-04-20T09:10-05:00"))
    assert len(d["groups"]["members_added"]) == 1


def test_case_graph_shape(api) -> None:
    g = _ok(api.get(f"/api/cases/{CASE}/graph?as_of=2026-04-20T10:00-05:00"))
    assert g["exists"] and {n["kind"] for n in g["nodes"]} >= {"case", "incident", "report"}
    assert {e["kind"] for e in g["edges"]} >= {"member_of", "report_of", "assessed"}


def test_eval_latest_404_then_newest_file(api) -> None:
    reports = Path(api.cfg.app.paths.reports)
    for p in reports.glob("eval_*.json"):
        p.unlink()
    assert api.get("/api/eval/latest").status_code == 404
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "eval_2026-10-01.json").write_text('{"metrics": {"a": 1}}')
    (reports / "eval_2026-10-02.json").write_text('{"metrics": {"a": 2}}')
    d = _ok(api.get("/api/eval/latest"))
    assert d["file"] == "eval_2026-10-02.json" and d["metrics"] == {"a": 2}


def test_schema_stream_returns_a_stream_message(api) -> None:
    d = _ok(api.get("/api/schema/stream"))
    assert d["message"]["type"] == "error"
