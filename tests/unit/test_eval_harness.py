"""SPEC §19.1-§19.4 harness: query sets, answerability, protocol and outputs (P1 nights)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from kairos_defense.cli import app
from kairos_defense.eval.harness import T_GRID, evaluate, night_of, query_sets
from kairos_defense.eval.report import gate, write_reports
from kairos_defense.eval.truth import track_truth
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.lance import LanceVectorStore


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
                        track_truth(cfg.app), "euclidean")  # fmt: skip


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
    worse = {"metrics": {k: (v * 2 if "latency" in k else v) for k, v in s["metrics"].items()}}
    worse["metrics"]["latency_prefilter_p95_ms"] = s["metrics"]["latency_prefilter_p95_ms"] / 2
    (tmp_path / "baseline.json").write_text(json.dumps(worse))
    assert any("latency_prefilter_p95_ms" in p for p in gate(s, tmp_path / "baseline.json"))


def test_cli_eval(p1_index, monkeypatch) -> None:
    import kairos_defense.cli as cli

    monkeypatch.setattr(cli, "_load_config", lambda _c: p1_index.cfg)
    runner = CliRunner()
    res = runner.invoke(app, ["eval", "--baseline"], terminal_width=200)
    assert res.exit_code == 0, res.output
    reports = Path(p1_index.cfg.app.paths.reports)
    assert (reports / "baseline.json").exists() and list(reports.glob("eval_*.md"))
    res = runner.invoke(app, ["eval"], terminal_width=200)  # same data: no regression
    assert res.exit_code == 0, res.output
    res = runner.invoke(app, ["eval", "--method", "dtw"])
    assert res.exit_code == 1 and "phase 4" in res.output
