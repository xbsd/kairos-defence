"""SPEC §10.7 explanations (D-074)."""

from __future__ import annotations

from kairos_defense.match.explain import reasons
from kairos_defense.match.fusion import FusionModel

FEATS = ("shape_sim", "rf_match", "bearing_sim", "tod_sim", "launch_sim", "radius_sim", "alt_sim")
CSIG = {"rf_family": "FAM-07", "approach_bearing_deg": 316.8, "loiter_radius_m": 183.0}


def model(**coef: float) -> FusionModel:
    base = dict.fromkeys(FEATS, 1.0) | coef
    return FusionModel("fusion-v1", FEATS, tuple(base[f] for f in FEATS), -5.0, 1.6, "h")


def x(**v: float) -> dict[str, float]:
    return dict.fromkeys(FEATS, 0.5) | {"shape_sim": 0.3} | v


def test_top_three_reasons_by_contribution() -> None:
    m = model(rf_match=5.0, tod_sim=4.0, bearing_sim=3.0, radius_sim=2.0, launch_sim=1.0)
    got = reasons(x(rf_match=1.0, tod_sim=1.0, bearing_sim=0.95, radius_sim=0.9, launch_sim=0.8),
                  m, 1.0, CSIG)  # fmt: skip
    assert got == ["Same RF family (FAM-07)", "Same time of night", "Same approach bearing (315°)"]
    m2 = model(rf_match=0.1, tod_sim=4.0, bearing_sim=3.0, radius_sim=9.0)
    got = reasons(x(rf_match=1.0, tod_sim=1.0, bearing_sim=0.95, radius_sim=0.9), m2, 1.0, CSIG)
    assert got == [
        "Same orbit radius (~180 m)",
        "Same time of night",
        "Same approach bearing (315°)",
    ]


def test_reasons_need_their_condition() -> None:
    m = model()
    assert reasons(x(rf_match=0.5, bearing_sim=0.9, radius_sim=0.8, launch_sim=0.7, tod_sim=0.9),
                   m, 1.05, CSIG) == []  # every value at (not above) its threshold  # fmt: skip
    assert reasons(x(launch_sim=0.71), m, float("nan"), CSIG) == ["Same launch area"]
    # a positive condition with a non-positive contribution is not a reason
    assert reasons(x(rf_match=1.0), model(rf_match=-1.0), 1.0, CSIG) == []
    assert reasons(x(bearing_sim=0.99), m, 1.0, {**CSIG, "approach_bearing_deg": None}) == []


def test_warp_reason_text() -> None:
    m = model(shape_sim=10.0)
    assert reasons(x(), m, 1.22, CSIG) == ["Same shape, flown 18% slower"]
    assert reasons(x(), m, 0.8, CSIG) == ["Same shape, flown 25% faster"]
    assert reasons(x(), m, 1.05, CSIG) == []
    assert reasons(x(), m, float("nan"), CSIG) == []


def test_reason_values_come_from_the_past_flight() -> None:
    m = model()
    got = reasons(x(rf_match=1.0, bearing_sim=0.99, radius_sim=0.95), m, 1.0, CSIG)
    assert set(got) == {"Same RF family (FAM-07)", "Same approach bearing (315°)",
                        "Same orbit radius (~180 m)"}  # fmt: skip
    north = reasons(x(bearing_sim=0.99), m, 1.0, {**CSIG, "approach_bearing_deg": 358.0})
    assert north == ["Same approach bearing (0°)"]


def test_contribution_table_sums_to_logit() -> None:
    import math

    import numpy as np

    from kairos_defense.match.explain import contribution_table

    m = model(rf_match=3.0, shape_sim=4.0, alt_sim=-0.5)
    feats = x(rf_match=1.0, shape_sim=0.9, alt_sim=0.2) | {"d_norm": 0.4, "window_s": 60.0}
    t = contribution_table(feats, m)
    assert [r["feature"] for r in t["rows"]][:2] == ["shape_sim", "rf_match"]
    assert {r["feature"] for r in t["rows"]} == set(FEATS)  # model features only
    mags = [abs(r["contribution"]) for r in t["rows"]]
    assert mags == sorted(mags, reverse=True)
    for r in t["rows"]:
        assert r["contribution"] == r["coefficient"] * r["value"]
    assert t["intercept"] == -5.0
    assert math.isclose(t["logit"], -5.0 + sum(r["contribution"] for r in t["rows"]))
    X = np.array([[feats[f] for f in FEATS]])
    assert math.isclose(t["score"], float(m.predict(X)[0]), rel_tol=1e-12)


def test_contribution_table_missing_feature_counts_zero() -> None:
    from kairos_defense.match.explain import contribution_table

    t = contribution_table({"shape_sim": 1.0}, model())
    rows = {r["feature"]: r for r in t["rows"]}
    assert rows["rf_match"]["value"] == 0.0 and rows["rf_match"]["contribution"] == 0.0
    assert t["rows"][0]["feature"] == "shape_sim"  # the only non-zero, then model order
    assert [r["feature"] for r in t["rows"][1:]] == list(FEATS[1:])
