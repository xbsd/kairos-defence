"""SPEC §10.5 fusion features and the §10.6 model artifact (D-073)."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from kairos_defense.match import fusion as fu

SIG = {  # a P1-like past flight (target-relative meters)
    "rf_family": "FAM-07", "approach_bearing_deg": 315.0, "tod_minutes": 1300,
    "launch_x_rel_m": -1450.0, "launch_y_rel_m": 1500.0, "loiter_radius_m": 180.0,
    "alt_median_m": 100.0,
}  # fmt: skip


def ctx(q: dict, c: dict) -> dict:
    return fu.context_frame(q, pd.DataFrame([c])).iloc[0].to_dict()


def test_rf_match_rules() -> None:
    assert fu.rf_match("FAM-07", "FAM-07") == 1.0
    assert fu.rf_match("FAM-07", "FAM-03") == 0.5  # same band (first digit, D-036)
    assert fu.rf_match("unknown", "FAM-07") == 0.5 and fu.rf_match("FAM-07", None) == 0.5
    assert fu.rf_match("unknown", "unknown") == 0.5
    assert fu.rf_match("FAM-07", "FAM-30") == 0.0  # P1 against C1
    assert fu.rf_match("FAM-11", "FAM-21") == 0.0


def test_bearing_and_tod_similarity() -> None:
    for d_brg, want in ((0.0, 1.0), (180.0, 0.0), (90.0, 0.5), (-90.0, 0.5)):
        got = ctx(SIG, {**SIG, "approach_bearing_deg": 315.0 + d_brg})["bearing_sim"]
        assert got == pytest.approx(want, abs=1e-12)
    assert ctx(SIG, {**SIG, "approach_bearing_deg": 5.0})["bearing_sim"] == pytest.approx(
        (1 + math.cos(math.radians(50))) / 2
    )  # 315° against 5° is 50° apart across north
    wrap = ctx({**SIG, "tod_minutes": 1430}, {**SIG, "tod_minutes": 1450})["tod_sim"]
    plain = ctx({**SIG, "tod_minutes": 1300}, {**SIG, "tod_minutes": 1320})["tod_sim"]
    assert (
        wrap == pytest.approx(plain) == pytest.approx((1 + math.cos(2 * math.pi * 20 / 1440)) / 2)
    )
    assert ctx({**SIG, "tod_minutes": 1300}, {**SIG, "tod_minutes": 2020})["tod_sim"] == (
        pytest.approx(0.0, abs=1e-12)
    )  # 12 h apart


def test_launch_radius_alt_and_unknowns() -> None:
    far = {**SIG, "launch_x_rel_m": SIG["launch_x_rel_m"] + 600.0,
           "launch_y_rel_m": SIG["launch_y_rel_m"] + 800.0}  # fmt: skip
    assert ctx(SIG, SIG)["launch_sim"] == pytest.approx(1.0)
    assert ctx(SIG, far)["launch_sim"] == pytest.approx(math.exp(-1.0))  # 1,000 m
    assert ctx({**SIG, "launch_x_rel_m": None, "launch_y_rel_m": None}, SIG)["launch_sim"] == 0.5
    assert ctx(SIG, {**SIG, "launch_x_rel_m": np.nan})["launch_sim"] == 0.5
    assert ctx(SIG, {**SIG, "loiter_radius_m": 230.0})["radius_sim"] == pytest.approx(math.exp(-1))
    assert ctx({**SIG, "loiter_radius_m": None}, SIG)["radius_sim"] == 0.5  # no loiter yet
    assert ctx(SIG, {**SIG, "loiter_radius_m": np.nan})["radius_sim"] == 0.5
    assert ctx(SIG, {**SIG, "alt_median_m": 160.0})["alt_sim"] == pytest.approx(math.exp(-2))
    assert ctx({**SIG, "approach_bearing_deg": None}, SIG)["bearing_sim"] == 0.5
    assert ctx({**SIG, "alt_median_m": None}, SIG)["alt_sim"] == 0.5


def test_context_frame_is_vectorized_and_keeps_the_index() -> None:
    rows = pd.DataFrame([SIG, {**SIG, "rf_family": "FAM-30"}], index=["a", "b"])
    out = fu.context_frame(SIG, rows)
    assert list(out.index) == ["a", "b"] and list(out.columns) == list(fu.CONTEXT)
    assert out.loc["a", "rf_match"] == 1.0 and out.loc["b", "rf_match"] == 0.0


def test_feature_order_follows_config(cfg) -> None:
    feats = fu.fusion_features(SIG, SIG, 0.4)
    order = cfg.scoring.fusion.features
    assert set(feats) == set(order)
    X = fu.feature_matrix([feats, {**feats, "shape_sim": 0.9}], order)
    assert X.shape == (2, 7) and X[1, order.index("shape_sim")] == 0.9
    rev = list(reversed(order))
    assert np.array_equal(fu.feature_matrix([feats], rev)[0], X[0][::-1])


def _model(cfg, coef=(4.0, 3.0, 1.5, 2.0, 1.0, 1.0, 1.0), b=-9.0) -> fu.FusionModel:
    return fu.FusionModel("fusion-v1", tuple(cfg.scoring.fusion.features), coef, b, 1.6, "h")


def test_model_round_trip(cfg, tmp_path) -> None:
    rng = np.random.default_rng(0)
    X = rng.uniform(size=(400, 7))
    y = (X @ np.array([3, 2, 1, 2, 1, 0.5, 0.5]) + rng.normal(0, 0.5, 400) > 5).astype(int)
    lr = LogisticRegression(class_weight="balanced", max_iter=1000).fit(X, y)
    coef = tuple(float(c) for c in lr.coef_[0])
    m = fu.FusionModel("fusion-v1", tuple(cfg.scoring.fusion.features), coef,
                       float(lr.intercept_[0]), 1.6, "abc", "2026-10-28T00:00:00",
                       {"t_grid": [45]}, {"roc_auc": 0.9})  # fmt: skip
    path = m.save(tmp_path / fu.MODEL_FILE)
    back = fu.FusionModel.load(path, cfg.scoring.fusion.features)
    assert back == m
    assert np.allclose(back.predict(X), lr.predict_proba(X)[:, 1], rtol=0, atol=1e-12)
    keys = set(json.loads(path.read_text()))
    assert {"version", "created_at", "features", "coefficients", "intercept", "tau",
            "training_hash", "validation"} <= keys  # fmt: skip
    cal = fu.DtwCalibration("dtw-calibration-v1", 1.6, 10, 2, {"p50": 1.6}, {"p50": 1.7}, 0.25,
                            [0.5, 1.5], "abc")  # fmt: skip
    assert fu.DtwCalibration.load(cal.save(tmp_path / fu.CALIBRATION_FILE)) == cal


def test_model_feature_order_mismatch_is_refused(cfg, tmp_path) -> None:
    path = _model(cfg).save(tmp_path / fu.MODEL_FILE)
    with pytest.raises(fu.ModelError, match="feature order"):
        fu.FusionModel.load(path, list(reversed(cfg.scoring.fusion.features)))
    with pytest.raises(fu.ModelError, match="make models"):
        fu.FusionModel.load(tmp_path / "missing.json", cfg.scoring.fusion.features)
    (tmp_path / "bad.json").write_text("{not json")
    with pytest.raises(fu.ModelError, match="make models"):
        fu.FusionModel.load(tmp_path / "bad.json", cfg.scoring.fusion.features)


def test_copycat_fuses_lower_than_true_p1(cfg) -> None:
    """A C1-like candidate copies P1's shape (high shape_sim) but flies FAM-30 from another
    launch area at another time of night: it must fuse below a true P1 flight."""
    m = _model(cfg)
    order = cfg.scoring.fusion.features
    c1 = {**SIG, "rf_family": "FAM-30", "launch_x_rel_m": 1800.0, "launch_y_rel_m": -900.0,
          "tod_minutes": 1500, "approach_bearing_deg": 150.0}  # fmt: skip
    p1 = {**SIG, "approach_bearing_deg": 318.0, "loiter_radius_m": 190.0, "alt_median_m": 108.0}
    x_p1 = fu.feature_matrix([fu.fusion_features(SIG, p1, 0.36)], order)
    x_c1 = fu.feature_matrix([fu.fusion_features(SIG, c1, 0.42)], order)  # an even closer shape
    assert m.predict(x_c1)[0] < m.predict(x_p1)[0]
    assert m.contributions(fu.fusion_features(SIG, c1, 0.42))["rf_match"] == 0.0
