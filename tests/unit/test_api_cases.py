"""SPEC §17.9 Case board, D-136: the case list, the known-then graph and recorded decisions."""

from __future__ import annotations

import pytest

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"


def _ok(r, code: int = 200):
    assert r.status_code == code, r.text
    return r.json()


@pytest.fixture
def fresh(api):
    _ok(api.post("/api/admin/reseed"))
    _ok(api.post("/api/admin/reset"))
    return api


def test_cases_list_has_the_planted_delta_case(fresh) -> None:
    cases = _ok(fresh.get("/api/cases"))
    c = next(c for c in cases if c["case_id"] == CASE)
    assert c["founder"] == DELTA and c["base"] == "DELTA" and c["status"] == "closed"
    assert c["claims"] == ["hobbyist"] and c["pending"] == 0 and c["members"] == [DELTA]
    assert c["opened_at"].endswith("Z")
    before = _ok(fresh.get("/api/cases?as_of=2026-04-20T09:00:00-05:00"))
    assert all(x["case_id"] != CASE for x in before)
    assert fresh.get("/api/cases?as_of=2026-04-20T09:00").status_code == 422  # naive time


def test_case_graph_known_then_10_local_has_hobbyist_and_no_links(fresh) -> None:
    g = _ok(fresh.get(f"/api/cases/{CASE}/graph?as_of=2026-04-20T10:00:00-05:00"))
    assessments = [n for n in g["nodes"] if n["kind"] == "assessment"]
    assert [n["label"] for n in assessments] == ["hobbyist"]
    members = [e for e in g["edges"] if e["kind"] == "member_of"]
    assert [(e["source"], e["target"]) for e in members] == [(DELTA, CASE)]  # the founder only
    assert not [e for e in g["edges"] if e["kind"] == "proposed"]
    assert g["status"] == "closed"


def test_decision_appends_decision_recorded_by_the_analyst(fresh) -> None:
    head = _ok(fresh.get("/api/ledger/verify"))["head_seq"]
    d = _ok(fresh.post(f"/api/cases/{CASE}/decisions",
                       json={"decision": "reopen", "analyst": "demo"}))  # fmt: skip
    assert d["decision"] == "reopen" and d["block"]["seq"] == head + 1
    assert d["block"]["event_type"] == "decision_recorded"
    assert d["block"]["actor"] == "analyst:demo"
    rec = _ok(fresh.get(f"/api/ledger/{head + 1}"))
    assert rec["object_json"]["decision"] == "reopen" and rec["case_id"] == CASE
    c = next(c for c in _ok(fresh.get("/api/cases")) if c["case_id"] == CASE)
    assert c["status"] == "open" and c["last_decision"] == "reopen"
    assert _ok(fresh.get("/api/ledger/verify"))["intact"] is True


def test_decision_unknown_value_422(fresh) -> None:
    head = _ok(fresh.get("/api/ledger/verify"))["head_seq"]
    r = fresh.post(f"/api/cases/{CASE}/decisions", json={"decision": "delete", "analyst": "demo"})
    assert r.status_code == 422
    bad = fresh.post(f"/api/cases/{CASE}/decisions", json={"decision": "close", "analyst": "a b"})
    assert bad.status_code == 422
    assert _ok(fresh.get("/api/ledger/verify"))["head_seq"] == head  # nothing written


def test_decision_unknown_case_404(fresh) -> None:
    r = fresh.post("/api/cases/CASE-NOPE/decisions", json={"decision": "close"})
    assert r.status_code == 404
