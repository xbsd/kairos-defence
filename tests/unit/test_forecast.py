"""SPEC §13: the analog forecast's pure steps (known answers) and the live forecast on the P1
nights."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from kairos_defense.features.channels import load_site
from kairos_defense.forecast.analog import (
    aligned_index,
    anchor_target,
    combine,
    forecast,
    remainder,
    resample_path,
    roads_crossing,
    rotate_rel,
    rotation_for,
)


def test_combine_known_answer() -> None:
    c, r = combine(np.array([[0.0, 0.0], [100.0, 0.0]]), np.array([1.0, 1.0]), 150, 1.5)
    assert np.allclose(c, [50, 0]) and r == 150  # RMS 50 m -> 75 m, below the floor
    c, r = combine(np.array([[0.0, 0.0], [400.0, 0.0]]), np.array([1.0, 1.0]), 150, 1.5)
    assert np.allclose(c, [200, 0]) and r == pytest.approx(300)  # RMS 200 m x 1.5


def test_weighted_center() -> None:
    c, r = combine(np.array([[0.0, 0.0], [400.0, 0.0]]), np.array([3.0, 1.0]), 150, 1.5)
    assert np.allclose(c, [100, 0])
    assert r == pytest.approx(1.5 * np.sqrt(0.75 * 100**2 + 0.25 * 300**2))
    c, _ = combine(np.array([[0.0, 0.0], [400.0, 0.0]]), np.array([0.0, 0.0]), 150, 1.5)
    assert np.allclose(c, [200, 0])  # no weight: equal weights


def test_rotation_only_beyond_30_degrees() -> None:
    assert rotation_for(20.0, 0.0) == 0.0
    assert rotation_for(350.0, 20.0) == 0.0  # 30 degrees apart across north
    assert rotation_for(90.0, 0.0) == 90.0
    assert rotation_for(0.0, 270.0) == 90.0  # wrap: the short way round
    assert rotation_for(None, 0.0) == 0.0 and rotation_for(90.0, float("nan")) == 0.0
    # a recovery due north of the target turns due east (clockwise, D-007)
    assert np.allclose(rotate_rel(np.array([[0.0, 100.0]]), 90.0), [[100.0, 0.0]])


def _flight(n: int = 400) -> np.ndarray:
    t = np.arange(n, dtype=np.float64)
    return np.column_stack([10 + 5 * np.sin(t / 20), 3 * np.cos(t / 15),
                            500 + 300 * np.sin(t / 40), 100 + 10 * np.sin(t / 30),
                            np.cos(t / 25)])  # fmt: skip


def test_aligned_index_on_a_shifted_copy(cfg) -> None:
    """Tonight's window is rows 100 to 159 of a flight; inside its anchored segment
    [70, 250) the last live row pairs with row 159 (± 2), with the shape distance's scaling."""
    f = _flight()
    lo, hi = 70, 250
    w, scales = cfg.scoring.features.channel_weights, cfg.scoring.features.channel_scales
    j = aligned_index(f[100:160], f[lo:hi], w, cfg.scoring.dtw.normalize, scales)
    assert abs(lo + j - 159) <= 2
    noisy = f + np.random.default_rng(3).normal(0, 0.02, f.shape) * scales  # radar-like noise
    assert abs(lo + aligned_index(noisy[100:160], f[lo:hi], w, "fixed", scales) - 159) <= 2
    assert aligned_index(f[:1], f[lo:hi], w) == hi - lo - 1


def test_exit_path_has_60_points_and_ends_at_recovery() -> None:
    gap = [False] * 7 + [True] + [False] * 2
    f = pd.DataFrame({"t_s": np.arange(10), "x_rel_m": np.arange(10) * 10.0,
                      "y_rel_m": np.zeros(10), "in_gap": gap})  # fmt: skip
    f.loc[8, "x_rel_m"] = np.nan
    rem = remainder(f, 4, (200.0, 0.0))
    assert rem.tolist() == [[50, 0], [60, 0], [90, 0], [200, 0]]  # gap and NaN rows dropped
    path = resample_path(rem)
    assert path.shape == (60, 2)
    assert np.allclose(path[0], [50, 0]) and np.allclose(path[-1], [200, 0])
    assert np.allclose(np.diff(path[:, 0]), 150 / 59)  # even by arc length
    assert np.allclose(resample_path(np.array([[1.0, 2.0]])), [[1.0, 2.0]] * 60)


def test_roads_crossing_the_zone() -> None:
    lines = {"Inside": LineString([(-500, 90), (500, 90)]),
             "Outside": LineString([(-500, 110), (500, 110)]),
             "Through": LineString([(0, -500), (0, 500)])}  # fmt: skip
    assert roads_crossing(np.array([0.0, 0.0]), 100.0, lines) == ["Inside", "Through"]


@pytest.fixture(scope="module")
def bravo(p1_index):
    from kairos_defense.store.duck import DuckTrackStore

    with DuckTrackStore(p1_index.cfg.app.paths.duckdb, p1_index.cfg.app) as duck:
        return load_site(duck, "BRAVO")


def test_anchor_modes(bravo) -> None:
    fence = bravo.target("BRAVO-fence")
    fuel = bravo.target("BRAVO-fuel_farm")
    assert anchor_target(fence, bravo, "munitions", "match_kind").asset_id == "BRAVO-munitions"
    assert anchor_target(fence, bravo, "munitions", "target") is fence
    assert anchor_target(fence, bravo, "fence", "match_kind") is fence
    assert anchor_target(fence, bravo, None, "match_kind") is fence
    for mode in ("target", "match_kind"):  # tonight on an asset: both modes agree
        assert anchor_target(fuel, bravo, "munitions", mode) is fuel


@pytest.fixture(scope="module")
def live(toy_models):
    """The live query at T+105 with the toy matcher's result."""
    from kairos_defense.match.matcher import DtwMatcher
    from kairos_defense.match.query import load_query
    from kairos_defense.store.duck import DuckTrackStore
    from kairos_defense.store.lance import LanceVectorStore

    cfg = toy_models
    duck = DuckTrackStore(cfg.app.paths.duckdb, cfg.app)
    q = load_query(duck, "DEMO-BRAVO-0828-T1", 105, cfg.scoring)
    res = DtwMatcher(duck, LanceVectorStore(cfg.app.paths.lancedb), cfg.scoring,
                     cfg.app.paths.models).match(q)  # fmt: skip
    yield cfg, duck, q, res
    duck.close()


def _with_recoveries(res, known: list[bool], ended: list[bool] | None = None):
    """``res`` cut to its first matches, with recovery points known or not and end times before
    or after the query's replay time."""
    from kairos_defense.match.matcher import MatchResult

    ms = res.matches[: len(known)]
    sigs = res.signatures.loc[[m.track_id for m in ms]].copy()
    for i, (m, k) in enumerate(zip(ms, known, strict=True)):
        sigs.loc[m.track_id, ["recovery_x_rel_m", "recovery_y_rel_m"]] = (
            (100.0 * (i + 1), -50.0) if k else (np.nan, np.nan))  # fmt: skip
        if ended is not None and not ended[i]:
            sigs.loc[m.track_id, "end_ts"] = pd.Timestamp("2100-01-01")
    return MatchResult(ms, [], {}, res.signature, sigs)


def test_top_k_counts_only_known_recoveries(live) -> None:
    cfg, duck, q, res = live
    r = _with_recoveries(res, [False, True, False, True, True, True])
    fc = forecast(duck, q, r, cfg.scoring)
    want = [r.matches[i].incident_id for i in (1, 3, 4)]
    assert [a.incident_id for a in fc.analogs] == want
    # a match still flying at the replay time has no known recovery yet (no look-ahead)
    r = _with_recoveries(res, [True] * 5, ended=[True, False, True, True, True])
    fc = forecast(duck, q, r, cfg.scoring)
    assert [a.incident_id for a in fc.analogs] == [r.matches[i].incident_id for i in (0, 2, 3)]


def test_no_known_recovery_gives_none(live) -> None:
    cfg, duck, q, res = live
    assert forecast(duck, q, _with_recoveries(res, [False] * 4), cfg.scoring) is None


def test_live_forecast_on_the_p1_nights(live) -> None:
    cfg, duck, q, res = live
    fc = forecast(duck, q, res, cfg.scoring)
    assert fc is not None and fc.at_s == 105 and fc.target_asset_id == q.target.asset_id
    assert np.isfinite([fc.center_x_m, fc.center_y_m]).all() and fc.radius_m >= 150
    assert fc.path.shape == (60, 2) and 1 <= len(fc.analogs) <= 3
    for a in fc.analogs:
        sig = duck.signature(a.track_id)
        assert np.isfinite([sig["recovery_x_rel_m"], sig["recovery_y_rel_m"]]).all()
    assert np.allclose(fc.path[-1], [fc.analogs[0].recovery_x_m, fc.analogs[0].recovery_y_m])
    d = json.loads(json.dumps(fc.to_dict()))
    assert set(d) >= {"center_x_m", "center_y_m", "radius_m", "path", "roads", "analogs"}
    assert len(d["path"]) == 60
    # the Euclidean baseline (no signatures handed over) reads them through the ports
    from kairos_defense.match.matcher import MatchResult

    plain = MatchResult(res.matches, res.baseline, {})
    again = forecast(duck, q, plain, cfg.scoring)
    assert again.to_dict() == fc.to_dict()
