"""The reveal's scoring (D-180): expectations per scenario and the verdict in words."""

from __future__ import annotations

from kairos_defense.eval.reveal import expectation, top_from, words


def rr(t, same, top_actor="P1", mimic=None, top_track="P1-A-T1", top_incident="P1-A", score=0.9):
    return {"t_s": t, "kind": "track", "first_same_rank": same, "mimic_rank": mimic,
            "top_incident": top_incident, "top_track": top_track, "top_actor": top_actor,
            "top_score": score}  # fmt: skip


def test_returning_prober_first_recognized_and_top_from() -> None:
    reruns = [rr(45, 2, "P3"), rr(50, 1), rr(55, 3, "P2"), rr(60, 1), rr(65, 1)]
    e = expectation("returning-prober", 1, reruns, 5, [], "P1", None)
    assert e["met"] and e["observed"] == "rank 2 at T+45 s"
    assert top_from(reruns) == 60
    assert words("P1", "County Rd operator", "returning-prober", 1, reruns, e, []) == (
        "P1, County Rd operator. First recognized at T+45 s (rank 2); top match from T+60 s."
    )


def test_returning_prober_missed_after_t120() -> None:
    reruns = [rr(45, None, "P3"), rr(120, 4, "P3"), rr(125, 1)]
    e = expectation("returning-prober", 1, reruns, 5, [], "P1", None)
    assert not e["met"] and "best same-actor rank by T+120 s: 4" in e["observed"]


def test_copycat_must_rank_above_the_actor_it_mimics_at_t120() -> None:
    ok = [rr(45, 6, mimic=1), rr(120, 2, mimic=4, top_actor="C1")]
    assert expectation("copycat", 1, ok, 15, [], "C1", "P1")["met"]
    below = [rr(45, 1, mimic=2), rr(120, 3, mimic=1)]  # only the latest rerun by T+120 counts
    e = expectation("copycat", 1, below, 15, [], "C1", "P1")
    assert not e["met"] and e["observed"] == "at T+120 s: C1 rank 3, P1 rank 1"
    none = [rr(120, None, mimic=None)]
    assert not expectation("copycat", 1, none, 15, [], "C1", "P1")["met"]


def test_hobbyist_reports_the_top_score() -> None:
    e = expectation("hobbyist", 1, [rr(45, None, "H-1", score=0.4123)], 0, [], "H-LIVE-1", None)
    assert e["met"] and "score 0.412" in e["observed"]


def test_swarm_repeat_ranks_the_team_first_at_the_final_rerun() -> None:
    sw = [rr(45, 2, "S2"), rr(300, 1, "S1", top_incident="S1-GOLF-260503", top_track=None)]
    e = expectation("swarm-repeat", 1, sw, 3, [], "S1", None)
    assert e["met"] and "S1-GOLF-260503" in e["observed"]
    assert words("S1", "Swarm team S1", "swarm-repeat", 1, sw, e, []) == (
        "S1, Swarm team S1. Its past event S1-GOLF-260503 ranked first."
    )
    assert not expectation("swarm-repeat", 1, sw[:1], 3, [], "S1", None)["met"]


def test_new_operator_twice_words_and_expectations() -> None:
    f1 = [rr(45, None, "P5", top_track="P5-X-T1")]
    e1 = expectation("new-operator-twice", 1, f1, 0, [], "N1", None)
    assert e1["met"]
    assert words("N1", "New operator", "new-operator-twice", 1, f1, e1, []) == (
        "N1, New operator. No earlier flights to find: this operator never flew before."
    )
    first = "LIVE-BRAVO-260902-221029-T1"
    f2 = [rr(45, 2, "P5"), rr(200, 1, "N1", top_track=first)]
    e2 = expectation("new-operator-twice", 2, f2, 1, [first], "N1", None)
    assert e2["met"]
    w = words("N1", "New operator", "new-operator-twice", 2, f2, e2, [first])
    assert first in w and "learned live" in w and "T+200 s" in w
    f2b = [rr(200, 3, "P5", top_track="P5-X-T1")]
    assert not expectation("new-operator-twice", 2, f2b, 1, [first], "N1", None)["met"]


def test_no_rerun_is_a_missed_expectation() -> None:
    e = expectation("hobbyist", 1, [], 0, [], "H-LIVE-1", None)
    assert e["met"] is False and "before any rerun" in e["observed"]
