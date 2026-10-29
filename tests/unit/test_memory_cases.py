"""D-136: ``case_summaries``, the Case board's list of cases as known at a moment."""

from __future__ import annotations

import pytest

from kairos_defense.memory.actions import decide_link
from kairos_defense.memory.asof import case_summaries
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import delta_story, local, proposal

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"


@pytest.fixture
def mem(cfg, tmp_path):
    with DuckCaseMemory(tmp_path / "mem.duckdb", cfg.app) as m:
        m.append_many(delta_story())
        yield m


def test_case_summaries_known_then_and_now(mem) -> None:
    assert case_summaries(mem.events(), local(2026, 4, 20, 9, 0)) == []  # not opened yet
    [then] = case_summaries(mem.events(), local(2026, 4, 20, 10, 0))
    assert then["case_id"] == CASE and then["founder"] == DELTA and then["base"] == "DELTA"
    assert then["status"] == "closed" and then["members"] == [DELTA] and then["pending"] == 0
    assert then["claims"] == ["hobbyist"] and then["last_decision"] == "close"
    assert then["opened_at"] == local(2026, 4, 20, 9, 10) and then["exports"] == 0

    t = local(2026, 8, 28, 21, 41, 30)
    seqs = mem.append_many([proposal(CASE, "P1-ALPHA-260303", "Q", 0.95, t, 1),
                            proposal(CASE, "P1-ALPHA-260502", "Q", 0.9, t, 2)])  # fmt: skip
    [mid] = case_summaries(mem.events(), t)
    assert mid["pending"] == 2 and mid["members"] == [DELTA]
    decide_link(mem, CASE, seqs[0], "approve", "test", t, "same operator")
    [now] = case_summaries(mem.events(), t)
    assert now["members"] == [DELTA, "P1-ALPHA-260303"] and now["pending"] == 1
    # the earlier moment is unchanged: the ledger is bitemporal, not overwritten
    assert case_summaries(mem.events(), local(2026, 4, 20, 10, 0)) == [then]
