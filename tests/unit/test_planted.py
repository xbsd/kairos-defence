"""Planted story items (SPEC §1.2, §8.10, §15.5, D-011): DELTA report, wrong label, swarms."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from kairos_defense.sim.calendar import utc_ms_to_local


def _local(g, base: str, ts) -> datetime:
    off = g.world.sites[base].utc_offset_hours
    return utc_ms_to_local(int(pd.Timestamp(ts).value // 1_000_000), off)


def test_planted_delta_report(cfg, planted) -> None:
    rep = planted.tables["reports"]
    mine = rep[rep.incident_id == "P1-DELTA-260419"]
    assert len(mine) == 1  # its only report (D-011)
    r = mine.iloc[0]
    for s in ("white pickup", "County Rd 12", "21:20", "22:05"):
        assert s in r.text, s
    want = cfg.scenario.p1_flights[2].reports[0]
    assert (r.source, r.source_grade) == ("security_forces", "B2") == (want.source, want.grade)
    assert _local(planted, "DELTA", r.report_ts) == datetime(2026, 4, 19, 22, 40)
    assert r.text.startswith("Security forces patrol observed a small drone near the fuel farm")
    ct = planted.truth["clue_truth"]
    rows = {
        (c.clue_type, c.clue_value, c.is_true) for c in ct[ct.report_id == r.report_id].itertuples()
    }
    assert {("vehicle", "white pickup", True), ("road", "County Rd 12", True)} <= rows


def test_planted_wrong_assessment(planted) -> None:
    a = planted.tables["assessments"].set_index("incident_id").loc["P1-DELTA-260419"]
    assert (a.label, a.author) == ("hobbyist", "DELTA BDOC")
    assert _local(planted, "DELTA", a.assessed_ts) == datetime(2026, 4, 20, 9, 10)
    truth = planted.truth["assessment_truth"].set_index("incident_id")
    assert truth.loc["P1-DELTA-260419"].correct_label == "probing"  # wrong on purpose


def test_planted_other_p1_flights_get_normal_paperwork(planted) -> None:
    rep = planted.tables["reports"]
    n = (rep.incident_id == "P1-ALPHA-260303").sum()
    assert 1 <= n <= 3
    a = planted.tables["assessments"].set_index("incident_id").loc["P1-ALPHA-260303"]
    assert a.author == "ALPHA BDOC" and a.label in ("unknown", "hobbyist")


@pytest.mark.parametrize(
    ("incident", "base", "status", "local"),
    [("S1-GOLF-260503", "GOLF", "history", datetime(2026, 5, 3, 22, 10)),
     ("DEMO-SWARM-ECHO-0614", "ECHO", "live", datetime(2026, 6, 14, 21, 50))],
)  # fmt: skip
def test_planted_swarm_events(planted, incident, base, status, local) -> None:
    inc = planted.tables["incidents"].set_index("incident_id").loc[incident]
    assert inc.installation_id == base and inc.status == status
    assert inc.is_swarm and inc.n_tracks == 5
    tt = planted.truth["track_truth"]
    mine = tt[tt.incident_id == incident]
    assert set(mine.actor_id) == {"S1"} and set(mine.actor_type) == {"swarm"}
    assert {_local(planted, base, t) for t in mine.launch_ts} == {local}
    reps = (planted.tables["reports"].incident_id == incident).sum()
    has_assessment = incident in set(planted.tables["assessments"].incident_id)
    if status == "live":
        assert reps == 0 and not has_assessment  # happening now (D-041)
    else:
        assert 2 <= reps <= 3 and has_assessment
        a = planted.tables["assessments"].set_index("incident_id").loc[incident]
        assert a.label == "swarm"


def test_planted_live_incidents_have_no_paperwork(g42, planted) -> None:
    for g, inc in ((g42, "DEMO-BRAVO-0828"), (planted, "DEMO-SWARM-ECHO-0614")):
        assert inc in set(g.tables["incidents"].incident_id)
        assert inc not in set(g.tables["reports"].incident_id)
        assert inc not in set(g.tables["assessments"].incident_id)
        assert inc in set(g.truth["assessment_truth"].incident_id)  # eval still knows the truth


def test_planted_rf_families(planted) -> None:
    fam = {}
    for inc in planted.incidents:
        if inc.plan.incident_id:
            fam[inc.incident_id] = {r.rf.family for r in inc.flights if len(r.rf)}
    assert fam["P1-DELTA-260419"] == fam["P1-ALPHA-260303"] == {"FAM-07"}
    assert fam["S1-GOLF-260503"] == {"FAM-30"}


def test_planted_live_t0_is_first_radar_contact(g42) -> None:
    """§1.2 and §16.1 agree: the mask hides the live drone from RF too, so the incident's first
    detection is its first radar point (D-039)."""
    assert g42.live is not None and g42.live.radar_lag_s == 0.0
    inc = next(i for i in g42.incidents if i.incident_id == "DEMO-BRAVO-0828")
    assert inc.start_ms == int(inc.radar_ms().min())
