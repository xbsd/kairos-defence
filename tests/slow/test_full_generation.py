"""Full-size generation (SPEC §8.11 volumes, §8.9 determinism). Run with ``make test-all``."""

from __future__ import annotations

import pytest

from kairos_defense.sim.datacard import EXPECTED, volumes
from kairos_defense.sim.generate import generate
from kairos_defense.sim.writers import table_hashes, write_all

pytestmark = pytest.mark.slow


def _app(cfg, folder):
    paths = cfg.app.paths.model_copy(
        update={"duckdb": folder / "kd.duckdb", "truth": folder / "gt.duckdb",
                "memory": folder / "mem.duckdb"}
    )  # fmt: skip
    return cfg.app.model_copy(update={"paths": paths})


@pytest.fixture(scope="module")
def full(cfg):
    return generate(cfg, 42)


def test_volumes_within_15_percent(full) -> None:
    v = volumes(full)
    for k in ("incidents", "tracks", "reports", "assessments"):
        assert 0.85 * EXPECTED[k] <= v[k] <= 1.15 * EXPECTED[k], (k, v[k])
    assert v["track_points"] > 400_000  # below §8.11's ≈1 M by design (D-030)
    assert v["rf_detections"] > 380_000  # below §8.11's ≈0.5 M for the same reason (D-044)


def test_full_swarms_and_paperwork(cfg, full) -> None:
    inc = full.tables["incidents"]
    teams = {s.id: s for s in cfg.actors.swarms}
    expected = sum(t.random_events for t in teams.values()) + len(cfg.scenario.swarm_events)
    assert int(inc.is_swarm.sum()) == expected
    history = inc[inc.status == "history"]
    assert set(full.tables["assessments"].incident_id) == set(history.incident_id)
    assert set(full.truth["assessment_truth"].incident_id) == set(inc.incident_id)
    rep = full.tables["reports"]
    assert (rep.incident_id == "P1-DELTA-260419").sum() == 1


def test_every_planted_flight_detected_and_live_on_time(cfg, full) -> None:
    ids = set(full.tables["incidents"].incident_id)
    assert {f.incident_id for f in cfg.scenario.p1_flights} <= ids
    lo, hi = cfg.scenario.expectations.live_first_contact_local
    assert lo <= full.live.first_contact_local <= hi
    a, b = cfg.scenario.expectations.live_orbit_established_s
    assert a <= full.live.orbit_established_s <= b


def test_full_run_is_deterministic(cfg, full, tmp_path_factory) -> None:
    a, b = tmp_path_factory.mktemp("a"), tmp_path_factory.mktemp("b")
    app_a, app_b = _app(cfg, a), _app(cfg, b)
    write_all(app_a, full.tables, full.truth)
    again = generate(cfg, 42)
    write_all(app_b, again.tables, again.truth)
    assert table_hashes(app_a.paths.duckdb) == table_hashes(app_b.paths.duckdb)
    assert table_hashes(app_a.paths.truth) == table_hashes(app_b.paths.truth)
