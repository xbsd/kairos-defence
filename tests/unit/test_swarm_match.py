"""Swarm choreography matching (SPEC §14) on generated nights (the ``swarm_index`` fixture: both
planted swarm events, three more S1 and three S2 events, written and indexed as `make index`
does)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kairos_defense.features.build import SWARM_TABLE
from kairos_defense.match.swarm import SwarmIndexMissing, SwarmMatcher, dtw_band, prefix_lengths
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore

DEMO = "DEMO-SWARM-ECHO-0614"
GOLF = "S1-GOLF-260503"


@pytest.fixture(scope="module")
def matcher(swarm_index):
    c, _ = swarm_index
    store = DuckTrackStore(c.app.paths.duckdb, c.app)
    yield SwarmMatcher(store, LanceVectorStore(c.app.paths.lancedb), c.scoring)
    store.close()


def test_index_writes_history_swarms_only(swarm_index) -> None:
    c, summary = swarm_index
    rows = LanceVectorStore(c.app.paths.lancedb).to_pandas(SWARM_TABLE)
    want = {"ECHO-260806-2049", "HOTEL-260829-0036", "JULIET-250325-2314",
            "JULIET-260316-2209", "JULIET-260511-0024", GOLF}  # fmt: skip
    assert set(rows.incident_id) == want and DEMO not in set(rows.incident_id)
    assert summary.swarm_incidents == 6 and summary.swarm_detected == 6
    assert rows.is_swarm.all() and (rows.together_s >= c.scoring.swarm.min_duration_s).all()
    assert len(rows.vector.iloc[0]) == 96
    with DuckTrackStore(c.app.paths.duckdb, c.app) as store:
        feats = store.sql("SELECT DISTINCT incident_id FROM swarm_features")
    assert set(feats.incident_id) == want and summary.swarm_seconds > 2000


def test_demo_swarm_top1_is_s1_golf(matcher) -> None:
    """SPEC §20 phase 9: the demo swarm's top 1 is S1-GOLF-260503."""
    res = matcher.match(DEMO)
    assert res.matches[0].incident_id == GOLF
    assert res.query.is_swarm and res.query.n_drones == 5
    sims = [m.similarity for m in res.matches]
    assert sims == sorted(sims, reverse=True) and all(0.0 < s <= 1.0 for s in sims)


def test_swarm_search_has_no_look_ahead(matcher) -> None:
    res = matcher.match(DEMO)
    start = res.query.start_ts
    assert res.matches and all(m.start_ts < start for m in res.matches)
    assert "ECHO-260806-2049" not in {m.incident_id for m in res.matches}  # flown later
    early = matcher.match(DEMO, at_s=120)
    assert early.query.descriptors.t_s.max() <= 120 and len(early.query.t_s) <= 121


def test_swarm_result_alignment(matcher) -> None:
    res = matcher.match(DEMO)
    top = res.matches[0]
    path = res.paths[top.incident_id]
    i, j = np.array(path).T
    assert (np.diff(i) >= 0).all() and (np.diff(j) >= 0).all()  # monotone
    assert path[0] == (0, 0) and path[-1] == (len(res.query.descriptors) - 1, top.matched_s - 1)
    aligned = res.aligned(top.incident_id)
    assert len(aligned) == len(res.query.descriptors) and aligned == sorted(aligned)
    assert top.warp_ratio == pytest.approx(top.matched_s / len(res.query.descriptors))
    rel = res.query.relative_positions()
    assert rel.shape == (5, len(res.query.t_s), 3)
    assert res.timings["total_ms"] > 0 and "dtw_ms" in res.timings


def test_swarm_path_cost_equals_the_full_dtw_distance(matcher) -> None:
    """The alignment is the optimal one, not only monotone: its cost is the DTW distance."""
    from kairos_defense.features.swarm_features import swarm_series
    from kairos_defense.match.dtw_rerank import series_distance

    res = matcher.match(DEMO)
    top = res.matches[0]
    q = swarm_series(res.query.descriptors)
    c = swarm_series(matcher.candidate_descriptors(top.incident_id).iloc[: top.matched_s])
    i, j = np.array(res.paths[top.incident_id]).T
    cost = float(np.sqrt(((q[i] - c[j]) ** 2).sum()))
    full = series_distance(q, c, max(len(q), len(c)))  # a band as wide as the series: no band
    assert cost == pytest.approx(full, rel=1e-9)


def test_an_s1_event_ranks_s1_first(matcher) -> None:
    res = matcher.match("ECHO-260806-2049")
    assert res.matches[0].incident_id == GOLF  # the only earlier S1 event on these nights


def test_short_query_returns_no_matches(matcher) -> None:
    res = matcher.match(DEMO, at_s=5)
    assert res.matches == []


def test_unknown_incident_raises(matcher) -> None:
    with pytest.raises(KeyError):
        matcher.match("NO-SUCH-INCIDENT")


def test_missing_swarm_index_is_reported(swarm_index, tmp_path) -> None:
    c, _ = swarm_index
    with DuckTrackStore(c.app.paths.duckdb, c.app) as store:
        m = SwarmMatcher(store, LanceVectorStore(tmp_path / "empty"), c.scoring)
        with pytest.raises(SwarmIndexMissing):
            m.match(DEMO)


def test_band_and_prefix_lengths() -> None:
    assert dtw_band(100, 100, 0.25) == 25
    assert dtw_band(100, 140, 0.25) == 41  # at least the length difference plus one
    lens = prefix_lengths(100, 500)
    assert lens[0] == 70 and lens[-1] == 140 and lens == sorted(set(lens))
    assert max(prefix_lengths(100, 90)) == 90  # clipped to the candidate's length
    assert isinstance(pd.Timestamp("2026-01-01"), pd.Timestamp)
