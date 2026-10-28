"""Assessments (SPEC §8.8, D-041, D-042): rules, planted error, timing and truth."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from kairos_defense.sim.assessments import CORRECT, DELAY_S, MISLABEL_P, assess


@pytest.fixture(scope="module")
def both(g42, planted):
    facts = {f.incident_id: f for f in g42.paper.facts + planted.paper.facts}
    assessments = {a.incident_id: a for a in g42.paper.assessments + planted.paper.assessments}
    return facts, assessments


def test_assessments_one_per_history_incident(g42, planted, both) -> None:
    facts, assessments = both
    for g in (g42, planted):
        ids = list(g.tables["assessments"].incident_id)
        assert len(ids) == len(set(ids))
        history = set(g.tables["incidents"].query("status == 'history'").incident_id)
        assert set(ids) == history
    assert all(facts[i].status == "history" for i in assessments)


def test_assessments_recorded_2_to_36_h_after_the_end(both) -> None:
    facts, assessments = both
    for iid, a in assessments.items():
        lag = (a.assessed_ms - facts[iid].end_ms) / 1000.0
        assert DELAY_S[0] <= lag <= DELAY_S[1], (iid, lag / 3600)
        assert a.assessment_id == f"A-{iid}"
        assert a.author == f"{facts[iid].installation_id} BDOC"


def test_assessments_label_rules(both) -> None:
    facts, assessments = both
    for iid, a in assessments.items():
        f = facts[iid]
        if iid == "P1-DELTA-260419":
            continue  # planted
        assert a.label != "probing"  # nobody has linked the flights yet
        if f.actor_type == "swarm":
            assert a.label == "swarm"
        elif f.rid_mode == "on" and f.rid_serial:
            assert a.label == "hobbyist" and f.rid_serial in a.rationale
        elif f.actor_type != "prober":
            assert a.label == "unknown", iid  # only probers get the 20% mislabel
        else:
            assert a.label in ("unknown", "hobbyist")


def test_assessments_mislabel_rate(planted) -> None:
    p1 = next(f for f in planted.paper.facts if f.incident_id == "P1-ALPHA-260303")
    labels = [assess(p1, np.random.default_rng(k)).label for k in range(4000)]
    assert np.mean([lab == "hobbyist" for lab in labels]) == pytest.approx(MISLABEL_P, abs=0.02)
    spoofed = replace(p1, rid_mode="spoofed", rid_serial="SN-0123456789ABCDEF")
    labels = [assess(spoofed, np.random.default_rng(k)).label for k in range(2000)]
    assert np.mean([lab == "hobbyist" for lab in labels]) == pytest.approx(MISLABEL_P, abs=0.03)
    copycat = replace(p1, actor_type="copycat")
    assert {assess(copycat, np.random.default_rng(k)).label for k in range(500)} == {"unknown"}
    copycat_on = replace(copycat, rid_mode="on", rid_serial="SN-0123456789ABCDEF")
    assert assess(copycat_on, np.random.default_rng(0)).label == "hobbyist"


def test_assessments_truth_labels(g42, planted) -> None:
    for g in (g42, planted):
        truth = g.truth["assessment_truth"].set_index("incident_id").correct_label
        assert set(truth.index) == set(g.tables["incidents"].incident_id)
        for f in g.paper.facts:
            assert truth.loc[f.incident_id] == CORRECT[f.actor_type]
    assert CORRECT == {"hobbyist": "hobbyist", "prober": "probing", "copycat": "probing",
                       "swarm": "swarm"}  # fmt: skip
