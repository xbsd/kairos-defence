"""Swarm view routes (SPEC §14, §17.9, D-153) with FastAPI's TestClient on the swarm nights."""

from __future__ import annotations

import pytest

from tests.conftest import with_paths

DEMO = "DEMO-SWARM-ECHO-0614"
GOLF = "S1-GOLF-260503"


def _ok(r, code: int = 200):
    assert r.status_code == code, r.text
    return r.json()


@pytest.fixture(scope="module")
def swarm_api(swarm_index, tmp_path_factory):
    from fastapi.testclient import TestClient

    from kairos_defense.api.app import create_app

    c, _ = swarm_index
    c = with_paths(c, tmp_path_factory.mktemp("swarm_api"), "memory", "live", "cache",
                   "exports", "key", "reports")  # fmt: skip
    with TestClient(create_app(c)) as client:
        yield client


def test_swarms_lists_both_demo_swarms(swarm_api) -> None:
    rows = _ok(swarm_api.get("/api/swarms"))
    by = {r["incident_id"]: r for r in rows}
    assert by[DEMO]["status"] == "live" and by[GOLF]["status"] == "history"
    assert by[DEMO]["n_tracks"] == 5 and by[DEMO]["start_ts"].endswith("Z")


def test_swarm_match_for_the_demo_swarm(swarm_api) -> None:
    head = _ok(swarm_api.get("/api/health"))["ledger_rows"]
    d = _ok(swarm_api.get(f"/api/swarm/{DEMO}"))
    assert d["matches"][0]["incident_id"] == GOLF and d["match_rank"] == 1
    q, m = d["query"], d["match"]
    assert q["is_swarm"] and q["n_drones"] == 5 and m["incident_id"] == GOLF
    n = len(q["curves"]["t_s"])
    assert len(d["aligned"]) == n and all(len(q["curves"][k]) == n for k in q["curves"])
    assert len(q["positions"]) == 5 and all(len(p) == len(q["t_s"]) for p in q["positions"])
    assert all(len(pt) == 3 for pt in q["positions"][0])
    assert max(d["aligned"]) < len(m["curves"]["t_s"])
    assert d["path"][0] == [0, 0] and d["path"][-1][0] == n - 1
    assert d["observed_s"] == q["t_s"][-1] and d["at_s"] is None
    assert _ok(swarm_api.get("/api/health"))["ledger_rows"] == head  # the encore writes nothing


def test_swarm_at_a_second_uses_only_points_up_to_it(swarm_api) -> None:
    d = _ok(swarm_api.get(f"/api/swarm/{DEMO}", params={"at": 120}))
    assert d["at_s"] == 120 and d["observed_s"] <= 120
    assert max(d["query"]["curves"]["t_s"]) <= 120


def test_swarm_selects_another_match_and_refuses_an_unknown_one(swarm_api) -> None:
    d = _ok(swarm_api.get(f"/api/swarm/{DEMO}"))
    other = d["matches"][1]["incident_id"]
    e = _ok(swarm_api.get(f"/api/swarm/{DEMO}", params={"match": other}))
    assert e["match"]["incident_id"] == other and e["match_rank"] == 2
    _ok(swarm_api.get(f"/api/swarm/{DEMO}", params={"match": "NOT-A-MATCH"}), 422)


def test_swarm_errors(swarm_api) -> None:
    _ok(swarm_api.get("/api/swarm/NO-SUCH-INCIDENT"), 404)
    _ok(swarm_api.get("/api/swarm/P1-DELTA-260419"), 422)  # a single-track incident


def test_swarm_results_are_cached_and_identical(swarm_api) -> None:
    a = _ok(swarm_api.get(f"/api/swarm/{DEMO}"))
    b = _ok(swarm_api.get(f"/api/swarm/{DEMO}"))
    assert a == b
