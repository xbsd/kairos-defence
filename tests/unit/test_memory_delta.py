"""SPEC §15.8 shift delta: rows recorded in (since, until], grouped, with evidence refs (D-101)."""

from __future__ import annotations

import json

import pytest

from kairos_defense.memory.actions import decide_link, propose_matches, retract
from kairos_defense.memory.delta import GROUPS, delta
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import assessment, delta_story, ev, incident, local, report

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"
SHIFT = (local(2026, 8, 28, 18, 0), local(2026, 8, 29, 6, 0))


def _top() -> list[dict]:
    return [{"incident_id": i, "score": s, "track_id": f"{i}-T1", "model_version": "fusion-v1"}
            for i, s in ((DELTA, 0.97), ("P1-ALPHA-260303", 0.93),
                         ("P1-CHARLIE-260710", 0.7))]  # fmt: skip


@pytest.fixture
def mem(cfg, tmp_path):
    with DuckCaseMemory(tmp_path / "mem.duckdb", cfg.app) as m:
        m.append_many(delta_story())
        t = local(2026, 8, 28, 21, 41)
        m.append(incident("DEMO-BRAVO-0828", "BRAVO", local(2026, 8, 28, 21, 20)))  # at 21:33
        m.append(report("R-DEMO-BRAVO-0828-1", "DEMO-BRAVO-0828", "BRAVO", t, t))
        m.append(ev("model_registered", t, object_json={"version": "fusion-v1", "sha256": "ab"}))
        _a, b, c = propose_matches(m, CASE, "DEMO-BRAVO-0828", _top(), t)
        decide_link(m, CASE, b, "approve", "duty", t)
        decide_link(m, CASE, c, "reject", "duty", t)
        yield m


def test_delta_groups_and_refs(mem) -> None:
    d = delta(mem.events(), *SHIFT)
    g = d.groups
    assert list(g) == list(GROUPS)
    assert [i["subject_id"] for i in g["incidents"]] == ["DEMO-BRAVO-0828"]
    assert [i["subject_id"] for i in g["reports"]] == ["R-DEMO-BRAVO-0828-1"]
    assert len(g["proposals"]) == 3 and len(g["models"]) == 1
    assert [i["subject_id"] for i in g["links_approved"]] == ["P1-ALPHA-260303"]
    assert [i["supersedes_seq"] for i in g["links_rejected"]] == [g["proposals"][2]["seq"]]
    assert g["assessments_added"] == g["decisions"] == g["exports"] == []
    seqs = {r["seq"] for r in mem.events()}
    for items in g.values():
        for i in items:
            assert i["seq"] in seqs and i["summary"] and i["recorded_at"] > SHIFT[0]
    assert d.count == 8 and d.head_seq == mem.head().seq
    assert json.loads(json.dumps(d.to_dict()))["count"] == 8


def test_delta_window_bounds(mem) -> None:
    rows = mem.events()
    t = local(2026, 8, 28, 21, 33)  # the live incident is recorded then (end + 5 min)
    assert delta(rows, t, SHIFT[1]).count == 7  # since is exclusive
    assert delta(rows, SHIFT[0], t).count == 1  # until is inclusive
    assert delta(rows, local(2026, 4, 20, 9, 9), local(2026, 4, 20, 9, 10)).groups[
        "decisions"][0]["event_type"] == "case_opened"  # fmt: skip


def test_delta_installation_filter(mem) -> None:
    rows = mem.events()
    bravo = delta(rows, *SHIFT, installation_id="BRAVO").groups
    assert len(bravo["incidents"]) == 1 and len(bravo["proposals"]) == 3  # query at BRAVO
    assert bravo["models"] == []  # no installation
    charlie = delta(rows, *SHIFT, installation_id="CHARLIE").groups
    assert [i["subject_id"] for i in charlie["proposals"]] == []  # no CHARLIE incident recorded
    delta_base = delta(rows, *SHIFT, installation_id="DELTA").groups
    assert len(delta_base["proposals"]) == 3  # all three target the DELTA case
    assert delta(rows, *SHIFT, installation_id="KILO").count == 0


def test_delta_contradictions_opened_in_window(mem) -> None:
    t = local(2026, 8, 28, 22, 0)
    seq = mem.append(assessment(DELTA, "probing", t, local(2026, 4, 19, 21, 35),
                                actor="analyst:a"))  # fmt: skip
    g = delta(mem.events(), *SHIFT).groups
    assert [(i["seq"], i["values"]) for i in g["contradictions_opened"]] == [
        (seq, ["hobbyist", "probing"])]  # fmt: skip
    assert len(g["assessments_added"]) == 1
    later = (SHIFT[1], local(2026, 8, 30, 6, 0))
    assert delta(mem.events(), *later).groups["contradictions_opened"] == []  # already open


def test_delta_assessment_retracted(mem) -> None:
    t = local(2026, 8, 28, 23, 0)
    links = [r for r in mem.events() if r["event_type"] == "link_approved"]
    retract(mem, 5, "analyst:a", t, "hobbyist was wrong")
    retract(mem, links[0]["seq"], "analyst:a", t, "linked by mistake")
    g = delta(mem.events(), *SHIFT).groups
    assert [(i["supersedes_seq"], i["retracts"]) for i in g["assessments_retracted"]] == [
        (5, "assessment_asserted")]  # fmt: skip
    assert [i["retracts"] for i in g["retractions"]] == ["link_approved"]
