"""SPEC §16.2, D-103, D-104: the live scratch tables and their DuckDB sink."""

from __future__ import annotations

from datetime import datetime

import pytest

from kairos_defense.store.ddl import LIVE_COLUMNS, RAW_COLUMNS
from kairos_defense.store.guard import TruthAccessError, connect_app_db
from kairos_defense.store.live_duck import DuckLiveSink, statement


def _pt(i: int) -> dict:
    return {"incident_id": "DEMO-X", "track_id": "DEMO-X-T1", "installation_id": "BRAVO",
            "region_id": "COASTAL", "sensor_id": "BRAVO-RADAR-1",
            "ts": datetime(2026, 8, 29, 2, 40, i), "x_m": 1.0 * i, "y_m": 2.0, "alt_m": 90.0,
            "quality": 0.9}  # fmt: skip


def test_live_tables_have_source_columns(cfg, tmp_path) -> None:
    with DuckLiveSink(tmp_path / "live.duckdb", cfg.app) as sink:
        for table, src in (("live_points", "track_points"), ("live_rf", "rf_detections"),
                           ("live_rid", "remote_id")):  # fmt: skip
            cols = [r[0] for r in sink.con.execute(f"DESCRIBE {table}").fetchall()]
            assert cols == RAW_COLUMNS[src] == LIVE_COLUMNS[table]


def test_append_returns_rows_total_write_ms_statement(cfg, tmp_path) -> None:
    with DuckLiveSink(tmp_path / "live.duckdb", cfg.app) as sink:
        a = sink.append("live_points", [_pt(1), _pt(2), _pt(3)])
        b = sink.append("live_points", [_pt(4)])
        assert (a.rows, a.total_rows, b.rows, b.total_rows) == (3, 3, 1, 4)
        assert a.statement == "INSERT INTO live_points … 3 rows" and a.write_ms > 0
        assert b.statement == statement("live_points", 1) == "INSERT INTO live_points … 1 row"
        assert sink.count("live_points") == 4
        got = sink.con.execute("SELECT x_m, ts FROM live_points ORDER BY x_m").fetchall()
        assert got[0] == (1.0, datetime(2026, 8, 29, 2, 40, 1))


def test_empty_batch_writes_nothing(cfg, tmp_path) -> None:
    with DuckLiveSink(tmp_path / "live.duckdb", cfg.app) as sink:
        s = sink.append("live_rf", [])
        assert (s.rows, s.total_rows, s.write_ms) == (0, 0, 0.0)
        with pytest.raises(ValueError, match="not a live table"):
            sink.append("ledger", [])


def test_reset_empties_only_live_tables(cfg, tmp_path) -> None:
    path = tmp_path / "live.duckdb"
    with DuckLiveSink(path, cfg.app) as sink:
        sink.con.execute("CREATE TABLE other (x INT)")
        sink.con.execute("INSERT INTO other VALUES (1)")
        sink.append("live_points", [_pt(1), _pt(2)])
        assert sink.reset() == {"live_points": 2, "live_rf": 0, "live_rid": 0}
        assert sink.count("live_points") == 0
        assert sink.con.execute("SELECT count(*) FROM other").fetchone()[0] == 1


def test_live_sink_refuses_truth_path(cfg, tmp_path) -> None:
    truth = tmp_path / "truth.duckdb"
    connect_app_db(truth, cfg.app).close()
    app = cfg.app.model_copy(update={"paths": cfg.app.paths.model_copy(update={"truth": truth})})
    with pytest.raises(TruthAccessError):
        DuckLiveSink(truth, app)
