"""SPEC §15.4 case diffs: events in (t1, t2] that touch the case's subjects, grouped (D-101)."""

from __future__ import annotations

import pytest

from kairos_defense.memory.actions import decide_link
from kairos_defense.memory.diff import GROUPS, case_diff, group
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import assessment, delta_story, ev, local, proposal, report

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"
THEN = local(2026, 4, 20, 9, 10)
NOW = local(2026, 8, 28, 21, 42)


@pytest.fixture
def mem(cfg, tmp_path):
    with DuckCaseMemory(tmp_path / "mem.duckdb", cfg.app) as m:
        m.append_many(delta_story())
        yield m


def _link(mem, inc: str, t, rank: int = 1) -> int:
    p = mem.append(proposal(CASE, inc, "DEMO-BRAVO-0828", 0.9, t, rank))
    decide_link(mem, CASE, p, "approve", "test", t)
    return p


def test_diff_window_is_t1_exclusive_t2_inclusive(mem) -> None:
    t = local(2026, 8, 28, 21, 41)
    p = _link(mem, "P1-ALPHA-260303", t)
    assert [i["seq"] for i in mem.diff(CASE, t, NOW)] == []
    assert [i["seq"] for i in mem.diff(CASE, THEN, t)] == [p, p + 1]
    assert mem.diff(CASE, local(2026, 4, 20, 9, 9), THEN)[0]["event_type"] == "case_opened"


def test_diff_groups(mem) -> None:
    t = local(2026, 8, 28, 21, 41)
    _link(mem, DELTA, t)
    _link(mem, "P1-ALPHA-260303", t, 2)
    mem.append(assessment(DELTA, "probing", t, local(2026, 4, 19, 21, 35), actor="analyst:a"))
    mem.append(ev("decision_recorded", t, case_id=CASE, subject_id=DELTA, predicate="decision",
                  actor="analyst:a", object_json={"decision": "reopen", "rationale": "linked",
                                                  "by": "analyst:a"}))  # fmt: skip
    mem.append(ev("evidence_exported", t, case_id=CASE, object_json={"manifest_sha256": "ab"}))
    g = group(mem.diff(CASE, THEN, NOW))
    assert list(g) == list(GROUPS)
    assert [(i["subject_id"], i["new_member"]) for i in g["members_added"]] == [
        (DELTA, False), ("P1-ALPHA-260303", True)]  # fmt: skip
    assert len(g["proposals"]) == 2 and len(g["claims_added"]) == 1
    assert [i["values"] for i in g["contradictions"]] == [["hobbyist", "probing"]]
    assert [i["event_type"] for i in g["decisions"]] == ["decision_recorded"]
    assert len(g["exports"]) == 1 and g["claims_retracted"] == []
    for i in mem.diff(CASE, THEN, NOW):
        assert {"seq", "event_type", "recorded_at", "summary", "supersedes_seq"} <= set(i)


def test_diff_includes_facts_of_members_added_later(mem) -> None:
    """P1-ALPHA-260502 had not happened at THEN; once linked, its incident and report show."""
    mem.append(report("R-P1-ALPHA-260502-1", "P1-ALPHA-260502", "ALPHA",
                      local(2026, 5, 2, 22, 0), local(2026, 5, 3, 1, 0)))  # fmt: skip
    t = local(2026, 8, 28, 21, 41)
    assert group(mem.diff(CASE, THEN, t))["facts"] == []  # not a member yet
    _link(mem, "P1-ALPHA-260502", t)
    facts = group(mem.diff(CASE, THEN, NOW))["facts"]
    assert [(i["event_type"], i["subject_id"]) for i in facts] == [
        ("incident_recorded", "P1-ALPHA-260502"),
        ("report_recorded", "R-P1-ALPHA-260502-1"),
    ]


def test_diff_empty_when_nothing_changed(mem) -> None:
    assert mem.diff(CASE, THEN, NOW) == []
    assert all(v == [] for v in group([]).values())


def test_port_diff_equals_pure_function(mem) -> None:
    _link(mem, "P1-ALPHA-260303", local(2026, 8, 28, 21, 41))
    assert mem.diff(CASE, THEN, NOW) == case_diff(mem.events(), CASE, THEN, NOW)
