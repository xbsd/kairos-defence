"""Full-size index and evaluation (SPEC §9, §19). Run with ``make test-all``."""

from __future__ import annotations

import numpy as np
import pytest

from kairos_defense.eval.harness import evaluate
from kairos_defense.eval.report import gate, write_reports
from kairos_defense.eval.truth import track_truth
from kairos_defense.features.build import WINDOWS_TABLE, build_index
from kairos_defense.sim.generate import generate
from kairos_defense.sim.writers import table_hashes, write_all
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore
from tests.conftest import tmp_config

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def indexed(cfg, tmp_path_factory):
    c = tmp_config(cfg, tmp_path_factory.mktemp("full"))
    g = generate(cfg, 42)
    write_all(c.app, g.tables, g.truth)
    return c, build_index(c)


def test_full_index_volumes(indexed) -> None:
    _, s = indexed
    assert s.history_tracks == s.signatures and not s.failed
    assert s.live_tracks_skipped == 6  # DEMO-BRAVO-0828 and the five ECHO swarm drones
    assert s.rf_unknown == 0
    assert sum(s.windows_by_size.values()) > 100_000
    assert s.loiter_dirs.get("ccw", 0) >= 20  # every P1 and C1 history flight


def test_full_index_is_deterministic(indexed) -> None:
    c, _ = indexed
    lance = LanceVectorStore(c.app.paths.lancedb)
    h1 = table_hashes(c.app.paths.duckdb)
    w1 = lance.to_pandas(WINDOWS_TABLE).sort_values("window_id").reset_index(drop=True)
    build_index(c)
    assert table_hashes(c.app.paths.duckdb) == h1
    w2 = lance.to_pandas(WINDOWS_TABLE).sort_values("window_id").reset_index(drop=True)
    assert w1.drop(columns="vector").equals(w2.drop(columns="vector"))
    assert np.array_equal(np.stack(w1.vector.to_numpy()), np.stack(w2.vector.to_numpy()))


def test_full_eval(indexed, tmp_path) -> None:
    c, _ = indexed
    with DuckTrackStore(c.app.paths.duckdb, c.app) as store:
        run = evaluate(c, store, LanceVectorStore(c.app.paths.lancedb), track_truth(c.app),
                       "euclidean")  # fmt: skip
    _, _, s = write_reports(run, tmp_path)
    n = s["counts"]
    assert n["prober_queries"] >= 20 and n["copycat_queries"] >= 8
    assert s["metrics"]["recall_at_5_t120"] is not None
    assert gate(s, tmp_path / "baseline.json") == []


def test_full_swarm_matching(indexed) -> None:
    """§14 and §19.3 on the full data (phase 9): the eight history swarms are indexed and
    detected, every answerable swarm query ranks its own team first (swarm_top1 >= 0.80) and the
    live demo swarm ranks S1-GOLF-260503 first."""
    from kairos_defense.eval.harness import query_sets, track_list
    from kairos_defense.eval.swarm import (
        incident_starts,
        incident_teams,
        swarm_cases,
        swarm_demo,
        swarm_metrics,
        swarm_outcomes,
    )
    from kairos_defense.match.swarm import SwarmMatcher

    c, s = indexed
    assert s.swarm_incidents == 8 and s.swarm_detected == 8
    truth = track_truth(c.app)
    with DuckTrackStore(c.app.paths.duckdb, c.app) as store:
        m = SwarmMatcher(store, LanceVectorStore(c.app.paths.lancedb), c.scoring)
        teams = incident_teams(truth)
        cases = swarm_cases(query_sets(track_list(store), truth).swarm_incidents,
                            incident_starts(store), teams)  # fmt: skip
        met = swarm_metrics(cases, swarm_outcomes(cases, m, teams, ()), ())
        row = swarm_demo(c, m)
    assert met["swarm_queries"] == 5 and met["swarm_unanswerable"] == 1
    assert met["swarm_top1"] >= 0.80
    assert row.status == "pass" and row.observed.startswith("#1 S1-GOLF-260503")
