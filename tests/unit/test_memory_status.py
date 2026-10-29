"""SPEC §17.8, D-116: the memory status shown beside each match."""

from __future__ import annotations

from kairos_defense.memory.views import UNATTRIBUTED, incident_statuses
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import delta_story, ev, local, proposal

CASE = "CASE-P1-DELTA-260419"
OFFSETS = {"DELTA": -5, "ALPHA": -5}


def _rows(cfg, tmp_path, extra=()):
    with DuckCaseMemory(tmp_path / "m.duckdb", cfg.app) as m:
        m.append_many(delta_story())
        for e in extra:
            m.append(e)
        return m.events()


def test_closed_as_hobbyist_on_apr_20(cfg, tmp_path) -> None:
    rows = _rows(cfg, tmp_path)
    s = incident_statuses(rows, local(2026, 8, 28, 21, 42), OFFSETS)
    assert s == {"P1-DELTA-260419": "Closed as hobbyist on Apr 20"}
    assert incident_statuses(rows, local(2026, 4, 20, 9, 0), OFFSETS) == {}  # before the case


def test_open_unattributed_without_case(cfg, tmp_path) -> None:
    s = incident_statuses(_rows(cfg, tmp_path), local(2026, 8, 28, 21, 42), OFFSETS)
    assert "P1-ALPHA-260502" not in s and UNATTRIBUTED == "Open, unattributed"


def test_open_case_counts_links(cfg, tmp_path) -> None:
    t = local(2026, 8, 28, 21, 42)
    reopen = ev("decision_recorded", t, case_id=CASE, subject_id="P1-DELTA-260419",
                predicate="decision", valid_from=t,
                object_json={"decision": "reopen", "rationale": "new", "by": "x"})  # fmt: skip
    prop = proposal(CASE, "P1-ALPHA-260303", "DEMO-X", 0.9, t)
    rows = _rows(cfg, tmp_path, [reopen, prop])
    approve = ev("link_approved", t, case_id=CASE, subject_id="P1-ALPHA-260303",
                 predicate="member_of", valid_from=t,
                 object_json={"proposal_seq": rows[-1]["seq"]})  # fmt: skip
    rows2 = _rows(cfg, tmp_path / "b", [reopen, prop, approve])
    s = incident_statuses(rows2, t, OFFSETS)
    assert s["P1-DELTA-260419"] == s["P1-ALPHA-260303"] == "Open case, 1 linked"
    assert incident_statuses(rows, t, OFFSETS)["P1-DELTA-260419"] == "Open case, 0 linked"
