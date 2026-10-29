"""SPEC §15.4: snapshots, contradictions, transaction time against valid time (D-094)."""

from __future__ import annotations

import json

import pytest

from kairos_defense.memory.actions import decide_link, retract
from kairos_defense.memory.asof import valid_at
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import assessment, delta_story, local, proposal

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"


@pytest.fixture
def mem(cfg, tmp_path):
    with DuckCaseMemory(tmp_path / "mem.duckdb", cfg.app) as m:
        m.append_many(delta_story())
        yield m


def test_case_unknown_before_it_is_opened(mem) -> None:
    s = mem.as_of(CASE, local(2026, 4, 20, 9, 0))
    assert not s.exists and s.status == "unknown" and s.members == [] and s.claims == []
    assert s.head_seq == 3  # two incidents and the report were already known


def test_known_then_shows_label_closed_no_links(mem) -> None:
    s = mem.as_of(CASE, local(2026, 4, 20, 9, 10))
    assert s.exists and s.status == "closed" and s.founder == DELTA
    assert s.members == [DELTA] and s.links == [] and s.pending == []
    assert [(c["value"], c["author"]) for c in s.claims] == [("hobbyist", "DELTA BDOC")]
    assert [d["decision"] for d in s.decisions] == ["close"]
    assert [r["report_id"] for r in s.reports] == ["R-P1-DELTA-260419-1"]
    assert s.contradictions == [] and s.head_seq == 6


def test_contradiction_keeps_both_claims_with_sources(mem) -> None:
    t = local(2026, 8, 28, 22, 0)
    mem.append(assessment(DELTA, "probing", t, local(2026, 4, 19, 21, 35), author="analyst a",
                          actor="analyst:a"))  # fmt: skip
    s = mem.as_of(CASE, t)
    assert len(s.contradictions) == 1
    c = s.contradictions[0]
    assert c["values"] == ["hobbyist", "probing"] and c["opened_seq"] == 8
    assert [(x["value"], x["actor"], x["recorded_at"]) for x in c["claims"]] == [
        ("hobbyist", "generator", local(2026, 4, 20, 9, 10)),
        ("probing", "analyst:a", t),
    ]
    assert {x["source_id"] for x in c["claims"]} == {f"A-{DELTA}"}


def test_retraction_resolves_contradiction_never_auto(mem) -> None:
    t = local(2026, 8, 28, 22, 0)
    mem.append(assessment(DELTA, "probing", t, local(2026, 4, 19, 21, 35), actor="analyst:a"))
    later = local(2026, 8, 29, 9, 0)
    assert len(mem.as_of(CASE, later).contradictions) == 1  # time alone resolves nothing
    retract(mem, 5, "analyst:a", later, "the hobbyist label was wrong")
    s = mem.as_of(CASE, later)
    assert s.contradictions == [] and [c["value"] for c in s.claims] == ["probing"]
    assert len(mem.as_of(CASE, t).contradictions) == 1  # history is unchanged


def test_approved_link_adds_member_and_clears_pending(mem) -> None:
    t = local(2026, 8, 28, 21, 41)
    p = mem.append(proposal(CASE, "P1-ALPHA-260303", "DEMO-BRAVO-0828", 0.91, t))
    s = mem.as_of(CASE, t)
    assert [x["seq"] for x in s.pending] == [p] and s.members == [DELTA]
    decide_link(mem, CASE, p, "approve", "test", t)
    s = mem.as_of(CASE, t)
    assert s.members == [DELTA, "P1-ALPHA-260303"] and s.pending == []
    assert [lk["proposal_seq"] for lk in s.links] == [p]
    assert s.status == "closed"  # linking never reopens a case (only a reopen decision does)


def test_rejected_proposal_is_no_longer_pending(mem) -> None:
    t = local(2026, 8, 28, 21, 41)
    p = mem.append(proposal(CASE, "P1-ALPHA-260502", "DEMO-BRAVO-0828", 0.6, t))
    decide_link(mem, CASE, p, "reject", "test", t, "different actor")
    s = mem.as_of(CASE, t)
    assert s.pending == [] and s.members == [DELTA]


def test_retracted_link_removes_member(mem) -> None:
    t = local(2026, 8, 28, 21, 41)
    p = mem.append(proposal(CASE, "P1-ALPHA-260303", "DEMO-BRAVO-0828", 0.91, t))
    link = decide_link(mem, CASE, p, "approve", "test", t)
    retract(mem, link, "analyst:test", t, "linked by mistake")
    s = mem.as_of(CASE, t)
    assert s.members == [DELTA] and s.links == [] and s.pending == []


def test_pending_excludes_existing_members(mem) -> None:
    t = local(2026, 8, 28, 21, 41)
    mem.append(proposal(CASE, DELTA, "DEMO-BRAVO-0828", 0.97, t))
    assert mem.as_of(CASE, t).pending == []


def test_valid_time_differs_from_transaction_time(mem) -> None:
    night = local(2026, 4, 19, 22, 0)
    now = local(2026, 8, 28, 21, 0)
    v = valid_at(mem.events(), CASE, night, now)
    assert [c["value"] for c in v["claims"]] == ["hobbyist"]  # true of that night, learned later
    assert "R-P1-DELTA-260419-1" in {r["subject_id"] for r in v["rows"]}
    assert not mem.as_of(CASE, night).exists  # nobody knew anything about the case that night
    early = valid_at(mem.events(), CASE, local(2026, 4, 19, 21, 0), now)
    assert early["claims"] == []  # the drone had not flown yet


def test_snapshot_head_and_to_dict_is_json(mem) -> None:
    s = mem.as_of(CASE, local(2026, 4, 25, 0, 0))
    rows = mem.events()
    assert (s.head_seq, s.head_hash) == (6, rows[5]["hash"])
    d = s.to_dict()
    text = json.dumps(d)
    assert d["as_of"] == "2026-04-25T05:00:00.000000Z"
    assert '"status": "closed"' in text and d["events"][0]["hash"] == rows[1]["hash"]
