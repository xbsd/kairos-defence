"""SPEC §16.4 ``GET /api/cases/{id}/graph``, D-108: case nodes and edges as known at a moment."""

from __future__ import annotations

from kairos_defense.memory.graph import case_graph
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import assessment, delta_story, ev, local, proposal

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"
NOW = local(2026, 8, 28, 21, 42)


def _rows(cfg, tmp_path, extra_fn=None):
    with DuckCaseMemory(tmp_path / "m.duckdb", cfg.app) as m:
        m.append_many(delta_story())
        if extra_fn:
            extra_fn(m)
        return m.events()


def _kinds(g, kind):
    return [n for n in g["nodes"] if n["kind"] == kind]


def test_graph_known_then_has_founder_report_assessment_no_links(cfg, tmp_path) -> None:
    g = case_graph(_rows(cfg, tmp_path), CASE, local(2026, 4, 20, 10, 0))
    assert g["exists"] and g["status"] == "closed"
    assert [n["id"] for n in _kinds(g, "incident")] == [DELTA]
    assert [n["id"] for n in _kinds(g, "report")] == ["R-P1-DELTA-260419-1"]
    assert [n["label"] for n in _kinds(g, "assessment")] == ["hobbyist"]
    assert [e["kind"] for e in g["edges"]].count("member_of") == 1
    assert {e["kind"] for e in g["edges"]} == {"member_of", "report_of", "assessed"}
    assert all(n["recorded_at"].endswith("Z") for n in g["nodes"])
    assert not case_graph(_rows(cfg, tmp_path / "b"), CASE, local(2026, 4, 1))["exists"]


def test_graph_after_approvals_has_three_member_edges(cfg, tmp_path) -> None:
    def approve(m):
        for inc in ("P1-ALPHA-260303", "P1-ALPHA-260502"):
            s = m.append(proposal(CASE, inc, "DEMO-BRAVO-0828", 0.9, NOW))
            m.append(ev("link_approved", NOW, case_id=CASE, subject_id=inc,
                        predicate="member_of", valid_from=NOW,
                        object_json={"proposal_seq": s}))  # fmt: skip
        m.append(proposal(CASE, "P1-CHARLIE-260710", "DEMO-BRAVO-0828", 0.8, NOW))

    g = case_graph(_rows(cfg, tmp_path, approve), CASE, NOW)
    members = [e["source"] for e in g["edges"] if e["kind"] == "member_of"]
    assert members == [DELTA, "P1-ALPHA-260303", "P1-ALPHA-260502"]
    pending = [e for e in g["edges"] if e["kind"] == "proposed"]
    assert [e["source"] for e in pending] == ["P1-CHARLIE-260710"] and pending[0]["score"] == 0.8
    inc = {n["id"]: n for n in _kinds(g, "incident")}
    assert inc["P1-ALPHA-260303"]["base"] == "ALPHA" and inc["P1-ALPHA-260303"]["member"]
    assert not inc["P1-CHARLIE-260710"]["member"]


def test_graph_flags_contradictions(cfg, tmp_path) -> None:
    def contradict(m):
        m.append(assessment(DELTA, "prober", NOW, local(2026, 4, 19, 21, 35), author="ANALYST",
                            actor="analyst:test"))  # fmt: skip

    g = case_graph(_rows(cfg, tmp_path, contradict), CASE, NOW)
    assert next(n for n in _kinds(g, "incident") if n["id"] == DELTA)["contradiction"]
    assert sorted(n["label"] for n in _kinds(g, "assessment")) == ["hobbyist", "prober"]
    assert all(n["contradiction"] for n in _kinds(g, "assessment"))
