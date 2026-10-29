"""SPEC §17.9 Match explainer, §10.7, D-135: ``GET /api/explain/{incident}/{track}``."""

from __future__ import annotations

import math

INC = "DEMO-BRAVO-0828"


def _ok(r, code: int = 200):
    assert r.status_code == code, r.text
    return r.json()


def _top(api, at: float = 90) -> dict:
    return _ok(api.get(f"/api/match/{INC}?at={at}"))["matches"][0]


def test_explain_contributions_reproduce_the_score(api) -> None:
    m = _top(api)
    d = _ok(api.get(f"/api/explain/{INC}/{m['track_id']}?at=90"))
    assert d["match"]["track_id"] == m["track_id"] and d["t_s"] == 90
    assert len(d["contributions"]) == 7
    logit = d["intercept"] + sum(r["contribution"] for r in d["contributions"])
    assert math.isclose(logit, d["logit"], abs_tol=1e-9)
    assert math.isclose(1 / (1 + math.exp(-logit)), m["score"], abs_tol=1e-9)
    assert math.isclose(d["score"], m["score"], abs_tol=1e-9)
    mags = [abs(r["contribution"]) for r in d["contributions"]]
    assert mags == sorted(mags, reverse=True)
    assert "memory_status" in d["match"] and d["model_version"] == m["model_version"]


def test_explain_tonight_path_stops_at_the_rerun_second(api) -> None:
    m = _top(api)
    d = _ok(api.get(f"/api/explain/{INC}/{m['track_id']}?at=93"))
    assert d["t_s"] == 90 and d["at"] == 93  # 93 snaps to the 90 s rerun
    ts = [p[0] for p in d["tonight"]["points"]]
    assert ts and max(ts) <= 90  # rule 3: nothing after the rerun second
    assert d["tonight"]["columns"] == ["t_s", "x_rel_m", "y_rel_m", "dist_target_m"]


def test_explain_past_segment_and_alignment_inside_the_track(api) -> None:
    m = _top(api)
    d = _ok(api.get(f"/api/explain/{INC}/{m['track_id']}?at=90"))
    ts = [p[0] for p in d["past"]["points"]]
    assert d["past"]["incident_id"] == m["incident_id"] and len(ts) > 60
    seg, al = d["segment"], d["alignment"]
    assert seg["start_s"] == m["window_offset_s"] and seg["end_s"] - seg["start_s"] == d["window_s"]
    assert min(ts) <= seg["start_s"] <= max(ts)
    assert al is not None and min(ts) <= al["start_s"] <= al["end_s"] <= max(ts)
    assert al["value"] >= 0


def test_explain_unknown_track_404(api) -> None:
    r = api.get(f"/api/explain/{INC}/NO-SUCH-TRACK?at=90")
    assert r.status_code == 404 and "not among the matches" in r.json()["detail"]
    assert api.get("/api/explain/NO-SUCH-INCIDENT/X?at=90").status_code == 404


def test_explain_before_first_rerun_404(api) -> None:
    m = _top(api)
    r = api.get(f"/api/explain/{INC}/{m['track_id']}?at=10")
    assert r.status_code == 404 and "no result" in r.json()["detail"]
