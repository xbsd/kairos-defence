"""SPEC §15.6 live writes: incidents, models, deduplicated proposals and analyst decisions
(D-097)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from kairos_defense.match.types import Match
from kairos_defense.memory.actions import (
    CaseExists,
    ProposalAlreadyDecided,
    ProposalNotFound,
    WrongCase,
    decide_link,
    json_safe,
    open_case,
    propose_matches,
    record_incident,
    register_model,
)
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import delta_story

CASE = "CASE-P1-DELTA-260419"
LIVE = "DEMO-BRAVO-0828"
T90 = datetime(2026, 8, 29, 2, 41, 36)


@pytest.fixture
def mem(cfg, tmp_path):
    with DuckCaseMemory(tmp_path / "mem.duckdb", cfg.app) as m:
        m.append_many(delta_story())
        yield m


def _m(inc: str, score: float, warp: float = 1.1) -> Match:
    return Match(LIVE, f"{inc}-T1", inc, inc.split("-")[1], datetime(2026, 1, 1), score, 0.8,
                 {"shape_sim": 0.8, "rf_match": 1.0}, ["Same RF family (FAM-07)"], warp, 0,
                 "fusion-v1")  # fmt: skip


TOP = [_m("P1-DELTA-260419", 0.97), _m("P1-ALPHA-260303", 0.93), _m("P1-CHARLIE-260710", 0.71)]


def _proposals(mem) -> list[dict]:
    return [r for r in mem.events() if r["event_type"] == "match_proposed"]


def test_record_incident_event_fields(mem) -> None:
    inc = {
        "incident_id": LIVE,
        "installation_id": "BRAVO",
        "region_id": "COASTAL",
        "start_ts": datetime(2026, 8, 29, 2, 40, 6),
        "n_tracks": 1,
        "is_swarm": False,
    }
    seq = record_incident(mem, inc, inc["start_ts"])
    r = mem.events()[-1]
    assert (r["seq"], r["actor"], r["subject_id"], r["valid_from"], r["valid_to"]) == (
        seq, "system", LIVE, inc["start_ts"], None)  # fmt: skip
    assert r["recorded_at"] == inc["start_ts"] and r["object_json"]["base"] == "BRAVO"
    assert record_incident(mem, inc, T90) == seq and mem.count() == 8


def test_register_model_once_per_version(mem) -> None:
    a = register_model(mem, "fusion-v1", "ab" * 32, T90, "models/fusion_v1.json", {"auc": 0.99})
    assert register_model(mem, "fusion-v1", "ab" * 32, T90 + timedelta(seconds=5)) == a
    b = register_model(mem, "fusion-v1", "cd" * 32, T90)
    assert b == a + 1 and mem.events()[-1]["object_json"]["sha256"] == "cd" * 32


def test_propose_matches_writes_one_event_per_top3_match(mem) -> None:
    ms = [*TOP[:2], _m("P1-CHARLIE-260710", 0.71, float("nan")), _m("P1-ALPHA-260502", 0.6)]
    seqs = propose_matches(mem, CASE, LIVE, ms, T90, query_track=f"{LIVE}-T1", t_s=90)
    assert seqs == [8, 9, 10]
    rows = _proposals(mem)
    assert [r["subject_id"] for r in rows] == ["P1-DELTA-260419", "P1-ALPHA-260303",
                                                "P1-CHARLIE-260710"]  # fmt: skip
    r = rows[1]
    o = r["object_json"]
    assert (r["actor"], r["case_id"], r["predicate"], r["confidence"], r["source_id"]) == (
        "matcher@fusion-v1", CASE, "member_of", 0.93, "fusion-v1")  # fmt: skip
    assert (o["query_incident"], o["query_track"], o["match_track"], o["rank"], o["t_s"]) == (
        LIVE, f"{LIVE}-T1", "P1-ALPHA-260303-T1", 2, 90)  # fmt: skip
    assert o["top3"] == [r["subject_id"] for r in rows] and o["reasons"]
    assert o["features"]["rf_match"] == 1.0 and o["model_version"] == "fusion-v1"
    assert rows[2]["object_json"]["warp_ratio"] is None  # NaN -> null
    assert {x["recorded_at"] for x in rows} == {T90}


def test_propose_skips_same_set_within_005(mem) -> None:
    propose_matches(mem, CASE, LIVE, TOP, T90)
    moved = [_m("P1-ALPHA-260303", 0.95), _m("P1-DELTA-260419", 0.93), TOP[2]]  # same set
    assert propose_matches(mem, CASE, LIVE, moved, T90 + timedelta(seconds=1)) == []
    assert len(_proposals(mem)) == 3


def test_propose_appends_when_score_moves_more_than_005(mem) -> None:
    propose_matches(mem, CASE, LIVE, TOP, T90)
    moved = [TOP[0], _m("P1-ALPHA-260303", 0.87), TOP[2]]
    assert len(propose_matches(mem, CASE, LIVE, moved, T90 + timedelta(seconds=1))) == 3


def test_propose_appends_on_set_change_and_skips_on_rerun(mem) -> None:
    propose_matches(mem, CASE, LIVE, TOP, T90)
    other = [TOP[0], TOP[1], _m("P1-ALPHA-260502", 0.70)]
    t120 = T90 + timedelta(seconds=30)
    assert len(propose_matches(mem, CASE, LIVE, other, t120)) == 3
    assert propose_matches(mem, CASE, LIVE, TOP, T90) == []  # seek back to T+90: known batch
    assert propose_matches(mem, CASE, LIVE, other, t120) == []  # a re-run of T+120
    assert propose_matches(mem, CASE, LIVE, [], t120) == []
    assert len(_proposals(mem)) == 6


def test_decide_link_approve_and_reject(mem) -> None:
    a, b, c = propose_matches(mem, CASE, LIVE, TOP, T90)
    ok = decide_link(mem, CASE, b, "approve", "duty_officer", T90, "same orbit")
    no = decide_link(mem, CASE, c, "reject", "duty_officer", T90, "different target")
    rows = {r["seq"]: r for r in mem.events()}
    assert rows[ok]["event_type"] == "link_approved" and rows[ok]["actor"] == "analyst:duty_officer"
    assert rows[ok]["object_json"] == {"proposal_seq": b, "query_incident": LIVE,
                                       "rationale": "same orbit"}  # fmt: skip
    assert rows[no]["event_type"] == "link_rejected" and rows[no]["supersedes_seq"] == c
    s = mem.as_of(CASE, T90)
    assert s.members == ["P1-DELTA-260419", "P1-ALPHA-260303"] and s.pending == []
    decide_link(mem, CASE, a, "approve", "duty_officer", T90)  # the founder: still decidable
    assert mem.as_of(CASE, T90).members == ["P1-DELTA-260419", "P1-ALPHA-260303"]


def test_decide_link_twice_or_wrong_case_raises(mem) -> None:
    a, b, _ = propose_matches(mem, CASE, LIVE, TOP, T90)
    decide_link(mem, CASE, a, "approve", "x", T90)
    decide_link(mem, CASE, b, "reject", "x", T90)
    for seq in (a, b):
        for d in ("approve", "reject"):
            with pytest.raises(ProposalAlreadyDecided):
                decide_link(mem, CASE, seq, d, "x", T90)
    with pytest.raises(ProposalNotFound):
        decide_link(mem, CASE, 1, "approve", "x", T90)  # an incident row
    with pytest.raises(ProposalNotFound):
        decide_link(mem, CASE, 999, "approve", "x", T90)
    with pytest.raises(WrongCase):
        decide_link(mem, "CASE-P1-ALPHA-260303", 10, "approve", "x", T90)
    with pytest.raises(ValueError, match="handle"):
        decide_link(mem, CASE, 10, "approve", "Person Name Example", T90)


def test_open_case_uses_case_dash_incident_and_refuses_existing(mem) -> None:
    seq = open_case(mem, "P1-ALPHA-260502", "analyst:a", T90, base="ALPHA")
    r = mem.events()[-1]
    assert (r["seq"], r["case_id"], r["subject_id"]) == (seq, "CASE-P1-ALPHA-260502",
                                                         "P1-ALPHA-260502")  # fmt: skip
    assert mem.as_of("CASE-P1-ALPHA-260502", T90).status == "open"
    with pytest.raises(CaseExists):
        open_case(mem, "P1-ALPHA-260502", "analyst:a", T90)
    with pytest.raises(CaseExists):
        open_case(mem, "P1-DELTA-260419", "analyst:a", T90)
    assert json_safe({"x": (float("inf"), 1)}) == {"x": [None, 1]}
