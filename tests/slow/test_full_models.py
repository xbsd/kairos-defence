"""Full-size fusion training and DTW evaluation (SPEC §10.6, §19). Run with ``make test-all``.

These assert structure, determinism and the copycat property; the §19.3 targets themselves are
judged by ``scripts/check_targets.py`` on the exit check's own run.
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
from kairos_defense.sim.generate import generate
from kairos_defense.sim.writers import write_all
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore
from tests.conftest import tmp_config

pytestmark = pytest.mark.slow

LIVE_EXPECTED = ("P1-DELTA-260419", "P1-ALPHA-260303", "P1-ALPHA-260502")


@pytest.fixture(scope="module")
def full(cfg, tmp_path_factory):
    c = tmp_config(cfg, tmp_path_factory.mktemp("full_models"))
    g = generate(cfg, 42)
    write_all(c.app, g.tables, g.truth)
    build_index(c)
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
    s = summarize(evaluate(c, duck, lance, truth, "dtw"))
    m = s["metrics"]
    for key in (
        "recall_at_5_t120",
        "dtw_lift",
        "copycat_first_t120",
        "recall_at_5_t120_baseline",
        "latency_prefilter_p95_ms",
        "latency_dtw_p95_ms",
        "latency_end_to_end_p95_ms",
    ):
        assert isinstance(m[key], float), key  # fmt: skip
    assert s["method"] == "dtw" and s["counts"]["prober_queries"] >= 20
    demo = {r["key"]: r["status"] for r in s["demo"]}
    assert demo["live_top3_incidents"] in ("pass", "fail")
    assert all(demo[k] for k in ("live_first_contact_local", "live_orbit_established_s"))
