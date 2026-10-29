"""Full-size fusion training, DTW evaluation, report recall and forecast (SPEC §10.6, §12, §13,
§19). Run with ``make test-all``.

These assert structure, determinism, the copycat property and the phase 5 demo beats; the §19.3
targets themselves are judged by ``scripts/check_targets.py`` on the exit check's own run.
"""

from __future__ import annotations

import pytest

from kairos_defense.eval.harness import evaluate
from kairos_defense.eval.report import summarize
from kairos_defense.eval.training import train_models
from kairos_defense.eval.truth import track_truth
from kairos_defense.features.build import build_index
from kairos_defense.match.matcher import DtwMatcher
from kairos_defense.match.query import load_query
from kairos_defense.recall.index import build_reports_index
from kairos_defense.sim.generate import generate
from kairos_defense.sim.writers import write_all
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceReportIndex, LanceVectorStore
from tests.conftest import tmp_config

pytestmark = pytest.mark.slow

LIVE_EXPECTED = ("P1-DELTA-260419", "P1-ALPHA-260303", "P1-ALPHA-260502")


@pytest.fixture(scope="module")
def full(cfg, tmp_path_factory):
    c = tmp_config(cfg, tmp_path_factory.mktemp("full_models"))
    g = generate(cfg, 42)
    write_all(c.app, g.tables, g.truth)
    build_index(c)
    build_reports_index(c)
    duck = DuckTrackStore(c.app.paths.duckdb, c.app)
    lance = LanceVectorStore(c.app.paths.lancedb)
    truth = track_truth(c.app)
    first = train_models(c, duck, lance, truth)
    yield c, duck, lance, truth, first
    duck.close()


def test_full_models_are_deterministic(full, tmp_path) -> None:
    c, duck, lance, truth, first = full
    again = train_models(c, duck, lance, truth, models_dir=tmp_path)
    assert again.model.training_hash == first.model.training_hash
    assert again.model.coefficients == first.model.coefficients
    assert again.model.intercept == first.model.intercept
    assert again.model.tau == first.model.tau == first.calibration.tau
    assert first.train["positives"] > 500 and first.model.validation["roc_auc"] > 0.9


def test_full_copycat_fuses_lower_than_p1(full) -> None:
    """Live query at T = 120 s: every C1 (copycat of P1) track that appears scores below the
    lowest of the three expected P1 flights."""
    c, duck, lance, truth, _ = full
    res = DtwMatcher(duck, lance, c.scoring, c.app.paths.models).match(
        load_query(duck, "DEMO-BRAVO-0828-T1", 120, c.scoring)
    )
    actor = truth.set_index("track_id")["actor_id"]
    p1 = [m.score for m in res.matches if m.incident_id in LIVE_EXPECTED]
    c1 = [m.score for m in res.matches if actor.loc[m.track_id] == "C1"]
    assert len(p1) == 3 and c1, "the copycat must be among the candidates for this to mean much"
    assert max(c1) < min(p1)


def test_full_eval_dtw(full, tmp_path) -> None:
    c, duck, lance, truth, _ = full
    reports = LanceReportIndex(c.app.paths.lancedb)
    s = summarize(evaluate(c, duck, lance, truth, "dtw", reports=reports))
    m = s["metrics"]
    for key in (
        "recall_at_5_t120",
        "dtw_lift",
        "copycat_first_t120",
        "recall_at_5_t120_baseline",
        "latency_prefilter_p95_ms",
        "latency_dtw_p95_ms",
        "latency_end_to_end_p95_ms",
        "report_linkage",
        "forecast_median_t90_m",
        "forecast_p80_t90_m",
        "latency_forecast_p95_ms",
        "latency_recall_p95_ms",
    ):
        assert isinstance(m[key], float), key  # fmt: skip
    assert s["method"] == "dtw" and s["counts"]["prober_queries"] >= 20
    assert m["report_linkage_relevant"] > 20 and m["forecast_missing_t90"] == 0
    demo = {r["key"]: r["status"] for r in s["demo"]}
    for key in ("live_top3_incidents", "live_rank1_report_for", "forecast_error_max_m"):
        assert demo[key] in ("pass", "fail"), key
    assert all(demo[k] for k in ("live_first_contact_local", "live_orbit_established_s"))


def test_full_demo_recall_and_forecast(full) -> None:
    """§20 phase 5 tests on the full data: at T+120 the planted DELTA report is rank 1 for the
    DELTA match with tonight's default query; at T+105 the forecast is within 400 m of the true
    recovery point and County Rd 12 crosses the zone; the report's County Rd 12 span is linked."""
    import numpy as np

    from kairos_defense.forecast.analog import forecast
    from kairos_defense.recall.embed import make_embedder
    from kairos_defense.recall.search import ReportRecall

    c, duck, lance, truth, _ = full
    matcher = DtwMatcher(duck, lance, c.scoring, c.app.paths.models)
    rr = ReportRecall(duck, LanceReportIndex(c.app.paths.lancedb), lance, make_embedder(c.app),
                      c.scoring)  # fmt: skip
    q = load_query(duck, "DEMO-BRAVO-0828-T1", 105, c.scoring)
    fc = forecast(duck, q, matcher.match(q), c.scoring)
    rec = truth.set_index("track_id").loc["DEMO-BRAVO-0828-T1"]
    err = float(np.hypot(fc.center_x_m - rec.recovery_x_m, fc.center_y_m - rec.recovery_y_m))
    assert err <= c.scenario.expectations.forecast_error_max_m, err
    assert "County Rd 12" in fc.roads
    q = load_query(duck, "DEMO-BRAVO-0828-T1", 120, c.scoring)
    res = matcher.match(q)
    fc = forecast(duck, q, res, c.scoring)
    out = rr.for_matches(q, res, fc.roads, n=3)
    delta = next(m for m in out.matches if m.incident_id == "P1-DELTA-260419")
    top = delta.reports[0]
    assert top.report_id == "R-P1-DELTA-260419-1"
    road = next(cl for cl in top.clues if cl.value == "County Rd 12")
    assert top.text[road.start : road.end] == "County Rd 12"
    assert "County Rd 12 runs through tonight's predicted zone." in road.links


def test_full_report_clues_equal_clue_truth(full) -> None:
    """Every vehicle and gazetteer-road clue the generator wrote is extracted, and nothing else
    of those two types (``report_clues`` against ``clue_truth``, true and false clues alike)."""
    from kairos_defense.eval.truth import clue_truth

    c, duck, _, _, _ = full
    got = set(map(tuple, duck.sql("SELECT * FROM report_clues").to_numpy().tolist()))
    roads = set(duck.sql("SELECT name FROM roads").name)
    ct = clue_truth(c.app)
    ct = ct[(ct.clue_type == "vehicle") | ((ct.clue_type == "road") & ct.clue_value.isin(roads))]
    assert got == set(zip(ct.report_id, ct.clue_type, ct.clue_value, strict=True))
    assert len(got) > 50
