"""Reports (SPEC §8.8, Appendix A): clue truth, delays, grades, counts, styles and clue rates."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from kairos_defense.sim import lexicon as lx
from kairos_defense.sim.reports import (
    COUNTS,
    SOURCES,
    make_reports,
    style,
)

N_SYNTH = 3000


@pytest.fixture(scope="module")
def both(g42, planted):
    """Reports, facts and tables of the three-week window and the planted nights together."""
    reports = g42.paper.reports + planted.paper.reports
    facts = {f.incident_id: f for f in g42.paper.facts + planted.paper.facts}
    clue_truth = pd.concat([g42.truth["clue_truth"], planted.truth["clue_truth"]])
    return reports, facts, clue_truth


def _facts(planted, incident_id: str):
    return next(f for f in planted.paper.facts if f.incident_id == incident_id)


def _synth(f, n: int = N_SYNTH, **change):
    f = replace(f, **change)
    out = []
    for k in range(n):
        out += make_reports(f, np.random.default_rng(k))
    return out


def test_reports_every_clue_has_a_truth_row(world, both) -> None:
    reports, _, clue_truth = both
    roads = [r.name for r in world.roads] + list(lx.MINOR_ROADS)
    parks = [lx.park_name(p.park_id) for p in world.parks]
    rows = clue_truth.groupby("report_id")
    with_clues = 0
    for r in reports:
        found = lx.find_clues(r.text, roads, parks)
        truth = set()
        if r.report_id in rows.groups:
            g = rows.get_group(r.report_id)
            truth = set(zip(g.clue_type, g.clue_value, strict=True))
        assert found == truth, (r.report_id, r.text)
        assert truth == {(c.type, c.value) for c in r.clues}
        with_clues += bool(truth)
    assert with_clues > 10
    assert set(clue_truth.clue_type) <= set(lx.CLUE_TYPES)


def test_reports_delays_within_source_ranges(both) -> None:
    reports, facts, _ = both
    for r in reports:
        lo, hi = SOURCES[r.source][0]
        delay = (r.report_ms - facts[r.incident_id].end_ms) / 1000.0
        assert lo <= delay <= hi, (r.report_id, r.source, delay)
        assert r.event_ms == facts[r.incident_id].start_ms


def test_reports_grades_from_source_lists(both) -> None:
    reports, _, _ = both
    for r in reports:
        assert r.grade in SOURCES[r.source][1], r.report_id


def test_reports_count_per_actor_type(both) -> None:
    reports, facts, _ = both
    n = Counter(r.incident_id for r in reports)
    for iid, f in facts.items():
        k = n[iid]
        if f.status == "live":
            assert k == 0, iid
        elif f.actor_type == "hobbyist":
            assert k in (0, 1), iid
        elif iid == "P1-DELTA-260419":
            assert k == 1
        else:
            lo, hi = COUNTS[f.actor_type]
            assert lo <= k <= hi, (iid, k)
    ids = [r.report_id for r in reports]
    assert len(ids) == len(set(ids))
    for iid, k in n.items():
        mine = sorted((r for r in reports if r.incident_id == iid), key=lambda r: r.report_id)
        assert [r.report_id for r in mine] == [f"R-{iid}-{j}" for j in range(1, k + 1)]
        assert [r.report_ms for r in mine] == sorted(r.report_ms for r in mine)


def test_reports_hobbyist_rate_and_variant(planted) -> None:
    hob = next(f for f in planted.paper.facts
               if f.actor_type == "hobbyist" and f.rid_mode == "on" and f.rid_serial)  # fmt: skip
    reps = _synth(hob)
    assert len(reps) / N_SYNTH == pytest.approx(0.4, abs=0.03)  # 60% none
    assert all(r.text.startswith("Operator located in") and hob.rid_serial in r.text for r in reps)
    assert {r.source for r in reps} == {"security_forces", "local_pd"}
    off = _synth(hob, rid_mode="off", rid_serial=None)
    assert not any(r.text.startswith("Operator located") for r in off)


def test_reports_clue_rates(planted) -> None:
    p1 = _facts(planted, "P1-ALPHA-260303")
    assert p1.vehicle == "white pickup" and p1.road == "County Rd 12"
    reps = [r for r in _synth(p1) if r.source in ("security_forces", "local_pd")]
    by = {t: [c for r in reps for c in r.clues if c.type == t] for t in lx.CLUE_TYPES}
    assert len(by["vehicle"]) / len(reps) == pytest.approx(0.35, abs=0.03)
    assert np.mean([c.is_true for c in by["vehicle"]]) == pytest.approx(0.8, abs=0.03)
    assert len(by["road"]) / len(reps) == pytest.approx(0.3, abs=0.03)
    assert np.mean([c.is_true for c in by["road"]]) == pytest.approx(0.8, abs=0.03)
    assert all(c.value == "County Rd 12" for c in by["road"] if c.is_true)
    sf = [r for r in reps if r.source == "security_forces"]
    for t in ("lights", "departure"):  # in every security-forces report
        assert sum(any(c.type == t for c in r.clues) for r in sf) == len(sf)
        assert np.mean([c.is_true for r in sf for c in r.clues if c.type == t]) == pytest.approx(
            0.8, abs=0.04
        )


def test_reports_actor_without_a_vehicle_gets_only_wrong_ones(planted) -> None:
    s1 = _facts(planted, "S1-GOLF-260503")
    assert s1.vehicle is None
    vehicles = [c for r in _synth(s1, 1500) for c in r.clues if c.type == "vehicle"]
    assert vehicles and not any(c.is_true for c in vehicles)


def test_reports_base_styles(planted) -> None:
    p1 = _facts(planted, "P1-ALPHA-260303")
    for base, want in (("ALPHA", "narrative"), ("BRAVO", "blotter"), ("CHARLIE", "terse")):
        assert style(base) == want
        sf = [r for r in _synth(p1, 300, installation_id=base) if r.source == "security_forces"]
        assert sf
        for r in sf:
            if want == "blotter":
                assert r.text == r.text.upper() and r.text.startswith("SF BLOTTER ")
            elif want == "narrative":
                assert r.text.startswith("Security forces patrol observed")
            else:
                assert " SF: patrol observed" in r.text


def test_reports_swarm_texts_say_formation(planted) -> None:
    s1 = replace(_facts(planted, "S1-GOLF-260503"), installation_id="ECHO")
    per_run = [make_reports(s1, np.random.default_rng(k)) for k in range(200)]
    assert {len(r) for r in per_run} == {2, 3}  # swarms: 2-3 reports
    for r in (r for run in per_run for r in run):
        if r.source in ("security_forces", "bdoc_log"):
            assert "formation" in r.text.lower(), r.text


def test_reports_llm_paraphrase_needs_phase_9(cfg, g42) -> None:
    from kairos_defense.sim.paperwork import paperwork

    on = cfg.model_copy(update={"app": cfg.app.model_copy(update={"reports_llm_paraphrase": True})})
    with pytest.raises(RuntimeError, match="phase 9"):
        paperwork(on, g42.world, g42.incidents, 42)
