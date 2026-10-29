"""SPEC §19.1-§19.4 harness: query sets, answerability, protocol and outputs (P1 nights)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from kairos_defense.cli import app
from kairos_defense.eval.harness import T_GRID, evaluate, night_of, query_sets
from kairos_defense.eval.report import gate, write_reports
from kairos_defense.eval.truth import track_truth
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceReportIndex, LanceVectorStore


def test_night_of() -> None:
    assert night_of(datetime(2026, 3, 1, 2, 0), -5) == date(2026, 2, 28)  # 21:00 local on 02-28
    assert night_of(datetime(2026, 3, 1, 6, 0), -5) == date(2026, 2, 28)  # 01:00 local, same night
    assert night_of(datetime(2026, 3, 2, 2, 0), -5) == date(2026, 3, 1)


def _row(tid, inc, start, status="history", swarm=False):
    return {"track_id": tid, "incident_id": inc, "installation_id": "ALPHA", "region_id": "R",
            "start_ts": pd.Timestamp(start), "status": status, "is_swarm": swarm,
            "utc_offset_hours": -5}  # fmt: skip


def test_query_sets() -> None:
    tracks = pd.DataFrame([
        _row("A1", "A1", "2025-06-01 02:00"),            # P9 earlier, before the window
        _row("A2", "A2", "2026-03-02 02:00"),            # P9 in the window: answerable
        _row("A3", "A3", "2026-03-01 02:00"),            # P8 night 02-28: outside
        _row("A4", "A4", "2026-04-01 02:00"),            # P8 in window, earlier P8 is A3
        _row("C1", "C1", "2026-05-01 02:00"),            # copycat, no earlier: unanswerable
        _row("L1", "L1", "2026-08-29 02:00", "live"),    # live: never a query
        _row("H1", "H1", "2026-05-02 02:00"),            # hobbyist: not a query
        _row("S1", "S", "2026-05-03 02:00", swarm=True),
        _row("S2", "S", "2026-05-03 02:00", swarm=True),
    ])  # fmt: skip
    truth = pd.DataFrame({"track_id": tracks.track_id,
                          "actor_id": ["P9", "P9", "P8", "P8", "C7", "P9", "H-1", "S1", "S1"],
                          "actor_type": ["prober"] * 4 + ["copycat", "prober", "hobbyist", "swarm",
                                                          "swarm"]})  # fmt: skip
    s = query_sets(tracks, truth)
    assert [q.track_id for q in s.probers] == ["A2", "A4"]
    assert all(q.answerable for q in s.probers)
    assert [(q.track_id, q.answerable) for q in s.copycats] == [("C1", False)]
    assert s.swarm_incidents == ["S"]


@pytest.fixture(scope="module")
def run(p1_index):
    cfg = p1_index.cfg
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        return evaluate(cfg, store, LanceVectorStore(cfg.app.paths.lancedb),
                        track_truth(cfg.app), "euclidean",
                        reports=LanceReportIndex(cfg.app.paths.lancedb))  # fmt: skip


def test_protocol_and_demo(run) -> None:
    p = run.outcomes["probers"]
    assert {q.track_id for q in run.sets.probers} >= {"P1-ALPHA-260303-T1", "P1-DELTA-260419-T1"}
    assert "DEMO-BRAVO-0828-T1" not in {q.track_id for q in run.sets.probers}  # live
    assert sorted({o.at_s for o in p}) == list(T_GRID)
    assert all(not o.ran for o in p if o.at_s == 30) and all(o.ran for o in p if o.at_s >= 45)
    demo = {r.key: r for r in run.demo}
    assert demo["live_first_contact_local"].status == "pass"
    assert demo["live_orbit_established_s"].status == "pass"
    assert demo["swarm_top1"].status.startswith("pending")


def test_outputs_and_gate(run, tmp_path: Path) -> None:
    md, js, s = write_reports(run, tmp_path)
    assert md.exists() and (tmp_path / "figures" / "eval_recall_by_t.png").exists()
    data = json.loads(js.read_text())
    assert data["metrics"]["recall_at_5_t120"] is not None and data["outcomes"]
    assert "Recall@5 at T = 120 s" in md.read_text()
    assert gate(s, tmp_path / "baseline.json") == []  # no baseline yet, demo checks pass
    worse = {  # latency_dtw_* are None for the Euclidean method
        "metrics": {
            k: (v * 2 if "latency" in k and v is not None else v) for k, v in s["metrics"].items()
        }
    }
    worse["metrics"]["latency_prefilter_p95_ms"] = s["metrics"]["latency_prefilter_p95_ms"] / 10
    jitter = {
        "metrics": {
            **s["metrics"],
            "latency_prefilter_p95_ms": s["metrics"]["latency_prefilter_p95_ms"] / 1.2,
        }
    }
    (tmp_path / "jitter.json").write_text(json.dumps(jitter))
    assert gate(s, tmp_path / "jitter.json") == []  # 20% timing noise is not a regression (D-060)
    (tmp_path / "baseline.json").write_text(json.dumps(worse))
    assert any("latency_prefilter_p95_ms" in p for p in gate(s, tmp_path / "baseline.json"))


def _with_reports(cfg, folder: Path):
    paths = cfg.app.paths.model_copy(update={"reports": str(folder)})
    return cfg.model_copy(update={"app": cfg.app.model_copy(update={"paths": paths})})


def test_cli_eval(p1_index, toy_models, tmp_path: Path, monkeypatch) -> None:
    """Replaces the phase 3 stub check (``eval --method dtw`` named phase 4)."""
    import kairos_defense.cli as cli

    runner = CliRunner()
    current = {"cfg": _with_reports(p1_index.cfg, tmp_path / "euclidean")}
    monkeypatch.setattr(cli, "_load_config", lambda _c: current["cfg"])
    res = runner.invoke(app, ["eval"], terminal_width=200)  # dtw is the default: needs models
    assert res.exit_code == 1 and "make models" in res.output, res.output
    res = runner.invoke(app, ["eval", "--method", "euclidean", "--baseline"], terminal_width=200)
    assert res.exit_code == 0, res.output
    reports = tmp_path / "euclidean"
    assert (reports / "baseline.json").exists() and list(reports.glob("eval_*.md"))
    res = runner.invoke(app, ["eval", "--method", "euclidean"], terminal_width=200)
    assert res.exit_code == 0, res.output  # same data: no regression
    # the DTW run in its own folder, before any baseline exists there
    current["cfg"] = _with_reports(toy_models, tmp_path / "dtw")
    res = runner.invoke(app, ["eval", "--method", "dtw"], terminal_width=200)
    assert res.exit_code in (0, 1), res.output  # 1 only for a failed demo assertion
    data = json.loads(next((tmp_path / "dtw").glob("eval_*.json")).read_text())
    assert data["method"] == "dtw" and isinstance(data["metrics"]["dtw_lift"], float)
    assert isinstance(data["metrics"]["report_linkage"], float)
    # phase 5: three demo rows assert under DTW; the run fails if and only if one of them fails
    failed = [r["key"] for r in data["demo"] if r["status"] == "fail"]
    assert (res.exit_code == 0) == (not failed), (res.output, failed)


@pytest.fixture(scope="module")
def dtw_run(toy_models):
    cfg = toy_models
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        return evaluate(cfg, store, LanceVectorStore(cfg.app.paths.lancedb),
                        track_truth(cfg.app), "dtw",
                        reports=LanceReportIndex(cfg.app.paths.lancedb))  # fmt: skip


def test_dtw_summary_keys(dtw_run, tmp_path: Path) -> None:
    _, js, s = write_reports(dtw_run, tmp_path)
    m = s["metrics"]
    assert s["method"] == "dtw" and s["model_version"] == "fusion-v1"
    assert s["candidate_tracks"] == 500
    for key in (
        "dtw_lift",
        "recall_at_5_t120_baseline",
        "latency_dtw_p50_ms",
        "latency_dtw_p95_ms",
        "latency_prefilter_p95_ms",
        "latency_end_to_end_p95_ms",
    ):
        assert isinstance(m[key], float), key  # fmt: skip
    assert m["dtw_lift"] == pytest.approx(m["recall_at_5_t120"] - m["recall_at_5_t120_baseline"])
    assert "dtw_lift" not in s["pending"]
    md = (tmp_path / js.name.replace(".json", ".md")).read_text()
    assert "DTW + fusion" in md and "DTW lift" in md
    p = [o for o in dtw_run.outcomes["probers"] if o.ran]
    assert all(o.candidates and o.dtw_ms is not None for o in p)


def test_demo_top3_is_an_assertion(dtw_run, run) -> None:
    dtw_demo = {r.key: r for r in dtw_run.demo}["live_top3_incidents"]
    assert dtw_demo.status in ("pass", "fail")
    assert "P1-DELTA-260419" in dtw_demo.observed
    euclid = {r.key: r for r in run.demo}["live_top3_incidents"]
    assert euclid.status.startswith("info")  # the baseline has no reasons (D-076)


def test_phase5_summary_keys(dtw_run, tmp_path: Path) -> None:
    _, js, s = write_reports(dtw_run, tmp_path)
    m = s["metrics"]
    for key in (
        "report_linkage",
        "forecast_median_t90_m",
        "forecast_p80_t90_m",
        "forecast_median_t120_m",
        "latency_forecast_p95_ms",
        "latency_recall_p95_ms",
    ):
        assert isinstance(m[key], float), key  # fmt: skip
    assert 0.0 <= m["report_linkage"] <= 1.0 and m["report_linkage_relevant"] > 0
    assert m["forecast_queries_t90"] == sum(o.at_s == 90 for o in dtw_run.outcomes["probers"])
    assert "report_linkage" not in s["pending"] and "forecast_error_t90" not in s["pending"]
    md = (tmp_path / js.name.replace(".json", ".md")).read_text()
    assert "Report linkage" in md and "Forecast and recall" in md
    assert (
        json.loads(js.read_text())["metrics"]["forecast_median_t90_m"] == m["forecast_median_t90_m"]
    )
    # only probers are labelled: copycat outcomes carry no forecast or linkage
    assert all(o.forecast_error_m is None for o in dtw_run.outcomes["copycats"])
    p = dtw_run.outcomes["probers"]
    assert all(o.forecast_error_m is not None for o in p if o.at_s in (90, 120))
    assert all(o.linkage_total is not None for o in p if o.at_s == 120)
    assert all(o.forecast_error_m is None and o.linkage_total is None for o in p
               if o.at_s not in (90, 120))  # fmt: skip


def test_demo_recall_and_forecast_rows(dtw_run, run) -> None:
    dtw_demo = {r.key: r for r in dtw_run.demo}
    rank1, fc = dtw_demo["live_rank1_report_for"], dtw_demo["forecast_error_max_m"]
    assert rank1.status in ("pass", "fail") and fc.status in ("pass", "fail")
    if rank1.status == "pass":
        assert rank1.observed.startswith("R-P1-DELTA-260419-1 rank 1")
        assert "County Rd 12" in rank1.observed and "white pickup" in rank1.observed
    assert fc.observed.split(" m ")[0].isdigit() and "radius" in fc.observed
    euclid = {r.key: r for r in run.demo}
    assert euclid["live_rank1_report_for"].status.startswith("info")
    assert euclid["forecast_error_max_m"].status.startswith("info")


def test_downstream_labels_use_filed_true_clue_reports(toy_models) -> None:
    from kairos_defense.eval.downstream import Downstream
    from kairos_defense.eval.truth import clue_truth
    from kairos_defense.match.matcher import DtwMatcher
    from kairos_defense.match.query import load_query

    cfg = toy_models
    lance = LanceVectorStore(cfg.app.paths.lancedb)
    truth = track_truth(cfg.app)
    with DuckTrackStore(cfg.app.paths.duckdb, cfg.app) as store:
        down = Downstream(cfg, store, lance, truth, LanceReportIndex(cfg.app.paths.lancedb))
        q = load_query(store, "P1-ALPHA-260502-T1", 120, cfg.scoring)
        res = DtwMatcher(store, lance, cfg.scoring, cfg.app.paths.models).match(q)
        hits, total, ms, rec = down.linkage(q, res)
        reports = store.sql("SELECT report_id, incident_id, report_ts FROM reports")
        fc, err, _ = down.forecast(q, res)
    true_ids = set(clue_truth(cfg.app).query("is_true").report_id)
    incs = [m.incident_id for m in rec.matches]
    want = reports[reports.incident_id.isin(incs) & reports.report_id.isin(true_ids)
                   & (reports.report_ts <= pd.Timestamp(q.until))]  # fmt: skip
    assert total == len(want) and 0 <= hits <= total and ms >= 0
    rel = down.relevant(incs, q.until)
    assert set().union(*rel.values()) == set(want.report_id) if rel else want.empty
    later = down.relevant(incs, pd.Timestamp("2000-01-01"))
    assert later == {}  # nothing is relevant before it was filed
    tr = truth.set_index("track_id").loc[q.track_id]
    assert err == pytest.approx(np.hypot(fc.center_x_m - tr.recovery_x_m,
                                         fc.center_y_m - tr.recovery_y_m))  # fmt: skip
