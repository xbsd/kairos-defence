"""SPEC §15.5 seeding on the generator's real output for the six P1 nights (D-096), and the §20
phase 6 tests: DELTA as of 2026-04-20 10:00 local, and three members after the demo links."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

import pytest

from kairos_defense.memory.actions import decide_link, propose_matches
from kairos_defense.memory.diff import group
from kairos_defense.memory.seed import SeedError, seed, seed_events
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import local

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"
THEN = local(2026, 4, 20, 9, 10)


@pytest.fixture
def store(seeded_p1):
    with DuckTrackStore(seeded_p1.cfg.app.paths.duckdb, seeded_p1.cfg.app) as s:
        yield s


def test_seed_counts_match_the_store(seeded_p1, store, ledger_copy) -> None:
    cut = seeded_p1.summary.cutoff
    q = {"c": cut}
    hist = "JOIN incidents i USING (incident_id) WHERE i.status <> 'live'"
    expected = {
        "incident_recorded": store.sql("SELECT count(*) n FROM incidents WHERE status <> 'live' "
                                       "AND end_ts + INTERVAL 5 MINUTE < $c", q).n[0],
        "report_recorded": store.sql(f"SELECT count(*) n FROM reports r {hist} "
                                     "AND r.report_ts < $c", q).n[0],
        "assessment_asserted": store.sql(f"SELECT count(*) n FROM assessments a {hist} "
                                         "AND a.assessed_ts < $c", q).n[0],
        "case_opened": 1, "decision_recorded": 1,
    }  # fmt: skip
    assert seeded_p1.summary.counts == expected
    rows = ledger_copy.events()
    assert dict(Counter(r["event_type"] for r in rows)) == expected
    assert seeded_p1.summary.rows == len(rows) == sum(expected.values())
    assert expected["incident_recorded"] > 10 and expected["report_recorded"] > 5


def test_seed_times_follow_15_5(store, ledger_copy) -> None:
    inc = store.sql("SELECT * FROM incidents").set_index("incident_id")
    rep = store.sql("SELECT * FROM reports").set_index("report_id")
    ass = store.sql("SELECT * FROM assessments").set_index("incident_id")
    for r in ledger_copy.events():
        assert r["actor"] == "generator"
        s = r["subject_id"]
        if r["event_type"] == "incident_recorded":
            row = inc.loc[s]
            assert r["recorded_at"] == row.end_ts + timedelta(minutes=5)
            assert (r["valid_from"], r["valid_to"]) == (row.start_ts, row.end_ts)
            assert r["object_json"]["base"] == row.installation_id
        elif r["event_type"] == "report_recorded":
            row = rep.loc[s]
            assert (r["recorded_at"], r["valid_from"], r["source_grade"]) == (
                row.report_ts, row.event_ts, row.source_grade)  # fmt: skip
            assert r["object_json"]["text"] == row.text
        elif r["event_type"] == "assessment_asserted":
            row = ass.loc[s]
            assert (r["recorded_at"], r["object_json"]["label"]) == (row.assessed_ts, row.label)
            assert r["valid_from"] == inc.loc[s].start_ts and r["predicate"] == "assessment"


def test_seed_is_ordered_and_cut_before_first_contact(seeded_p1, ledger_copy) -> None:
    rows = ledger_copy.events()
    times = [r["recorded_at"] for r in rows]
    assert times == sorted(times)
    assert max(times) < seeded_p1.summary.cutoff
    live = {seeded_p1.cfg.scenario.live_incident, "DEMO-SWARM-ECHO-0614"}
    assert not live & {r["subject_id"] for r in rows}
    assert not live & {(r["object_json"] or {}).get("incident_id") for r in rows}


def test_planted_delta_trio_in_order_at_0910_local(seeded_p1, ledger_copy) -> None:
    trio = [r for r in ledger_copy.events() if r["subject_id"] == DELTA
            and r["event_type"] != "incident_recorded"]  # fmt: skip
    assert [r["event_type"] for r in trio] == ["case_opened", "assessment_asserted",
                                               "decision_recorded"]  # fmt: skip
    assert [r["seq"] for r in trio] == [trio[0]["seq"] + i for i in range(3)]
    planted = next(f for f in seeded_p1.cfg.scenario.p1_flights if f.incident_id == DELTA)
    expected = planted.assessment.assessed_local + timedelta(hours=5)  # COASTAL is UTC-5
    assert {r["recorded_at"] for r in trio} == {expected} == {THEN}
    assert trio[2]["object_json"]["decision"] == "close"
    assert trio[2]["object_json"]["rationale"] == "assessed hobbyist"
    assert trio[0]["case_id"] == CASE and trio[1]["object_json"]["author"] == "DELTA BDOC"


def test_delta_known_at_1000_local_hobbyist_closed_no_links(ledger_copy) -> None:
    """SPEC §20 phase 6: the DELTA case as of 2026-04-20 10:00 local."""
    s = ledger_copy.as_of(CASE, local(2026, 4, 20, 10, 0))
    assert s.exists and s.status == "closed"
    assert [c["value"] for c in s.claims] == ["hobbyist"]
    assert s.links == [] and s.pending == [] and s.members == [DELTA]
    assert "R-P1-DELTA-260419-1" in {r["report_id"] for r in s.reports}
    assert s.contradictions == []


def test_delta_case_unknown_at_0900_local(ledger_copy) -> None:
    s = ledger_copy.as_of(CASE, local(2026, 4, 20, 9, 0))
    assert not s.exists and s.status == "unknown" and s.head_seq is not None


def test_no_cross_base_links_in_history(ledger_copy) -> None:
    rows = ledger_copy.events()
    kinds = {r["event_type"] for r in rows}
    assert not kinds & {"match_proposed", "link_approved", "link_rejected", "claim_retracted"}
    assert {r["case_id"] for r in rows if r["case_id"]} == {CASE}


def test_seed_is_deterministic(seeded_p1, store, tmp_path) -> None:
    with DuckCaseMemory(tmp_path / "again.duckdb", seeded_p1.cfg.app) as mem:
        s = seed(mem, store, seeded_p1.cfg.scenario)
    assert (s.head_seq, s.head_hash) == (seeded_p1.summary.head_seq, seeded_p1.summary.head_hash)
    assert seed_events(store, seeded_p1.cfg.scenario) == seed_events(store, seeded_p1.cfg.scenario)


def test_seed_refuses_non_empty_ledger(seeded_p1, store, ledger_copy) -> None:
    n = ledger_copy.count()
    with pytest.raises(SeedError, match="reseed"):
        seed(ledger_copy, store, seeded_p1.cfg.scenario)
    assert ledger_copy.count() == n


def test_three_demo_links_make_three_members_and_diff_lists_them(seeded_p1, store,
                                                                 ledger_copy) -> None:  # fmt: skip
    """SPEC §20 phase 6: approve the scenario's three demo links (hand-written proposals at
    T+90, so the test does not depend on the matcher); the case shows three members and the diff
    lists them, with what ALPHA-260502 brought ("it had not happened yet" at THEN)."""
    sc = seeded_p1.cfg.scenario
    top3 = sc.expectations.live_top3_incidents
    now = seeded_p1.summary.cutoff + timedelta(seconds=sc.expectations.live_top3_at_s)
    ms = [{"incident_id": inc, "score": s, "track_id": f"{inc}-T1", "model_version": "test"}
          for inc, s in zip(top3, (0.97, 0.93, 0.88), strict=True)]  # fmt: skip
    seqs = propose_matches(ledger_copy, CASE, sc.live_incident, ms, now, t_s=90,
                           actor="matcher@test")  # fmt: skip
    assert len(seqs) == 3
    for p in seqs:
        decide_link(ledger_copy, CASE, p, "approve", "test", now, "same pattern")
    s = ledger_copy.as_of(CASE, now)
    assert sorted(s.members) == sorted(top3) and len(s.members) == 3 and s.pending == []
    assert s.status == "closed"  # only an analyst's reopen changes it
    g = group(ledger_copy.diff(CASE, THEN, now))
    assert sorted(i["subject_id"] for i in g["members_added"]) == sorted(top3)
    assert {i["subject_id"]: i["new_member"] for i in g["members_added"]} == {
        DELTA: False, "P1-ALPHA-260303": True, "P1-ALPHA-260502": True}  # fmt: skip
    assert sorted(i["subject_id"] for i in g["proposals"]) == sorted(top3)
    later = "P1-ALPHA-260502"
    reports = set(store.sql("SELECT report_id FROM reports WHERE incident_id = $i",
                            {"i": later}).report_id)  # fmt: skip
    facts = {(i["event_type"], i["subject_id"]) for i in g["facts"]}
    assert facts == {("incident_recorded", later)} | {("report_recorded", r) for r in reports}
    assert [i["subject_id"] for i in g["claims_added"]] == [later]
    assert ledger_copy.verify_chain() is None
