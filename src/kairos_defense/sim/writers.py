"""DuckDB writers (SPEC §8.11). The only module that writes the ground-truth file.

``write_all`` drops and recreates the app database and ``truth.duckdb`` from the §7 DDL, then
bulk-inserts each in-memory table (``con.register`` then ``INSERT ... SELECT``). It also deletes
``memory.duckdb``, which phase 6 defines (D-029). ``table_hashes`` gives one SHA-256 per table,
over rows ordered by every column, for the determinism tests (§8.9).
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Sequence
from pathlib import Path

import duckdb
import pandas as pd

from kairos_defense.config import AppConfig
from kairos_defense.store.ddl import RAW_COLUMNS, RAW_DDL, TRUTH_COLUMNS, TRUTH_DDL
from kairos_defense.store.guard import connect_app_db

log = logging.getLogger(__name__)


def _remove(path: Path) -> None:
    for p in (path, path.with_name(path.name + ".wal")):
        if p.exists():
            p.unlink()


def _write(con: duckdb.DuckDBPyConnection, ddl: dict[str, str], columns, tables) -> dict[str, int]:
    counts = {}
    for name, sql in ddl.items():
        con.execute(sql)
        df = tables.get(name)
        if df is None or len(df) == 0:
            counts[name] = 0
            continue
        if list(df.columns) != columns[name]:
            raise ValueError(f"{name}: columns {list(df.columns)} do not match the DDL")
        con.register("df_in", df)
        con.execute(f"INSERT INTO {name} SELECT * FROM df_in")
        con.unregister("df_in")
        counts[name] = len(df)
    return counts


def write_all(
    app: AppConfig, raw: dict[str, pd.DataFrame], truth: dict[str, pd.DataFrame]
) -> dict[str, dict[str, int]]:
    """Recreate the app and truth databases from scratch; returns row counts per table."""
    raw_path, truth_path, memory_path = (Path(p) for p in (app.paths.duckdb, app.paths.truth,
                                                            app.paths.memory))  # fmt: skip
    for p in (raw_path, truth_path, memory_path):
        p.parent.mkdir(parents=True, exist_ok=True)
        _remove(p)
    con = connect_app_db(raw_path, app)
    try:
        raw_counts = _write(con, RAW_DDL, RAW_COLUMNS, raw)
    finally:
        con.close()
    con = duckdb.connect(str(truth_path))  # the one writer of truth (CLAUDE.md rule 2)
    try:
        truth_counts = _write(con, TRUTH_DDL, TRUTH_COLUMNS, truth)
    finally:
        con.close()
    log.info("wrote %s and %s", raw_path, truth_path)
    return {"raw": raw_counts, "truth": truth_counts}


def table_hashes(path: Path | str) -> dict[str, str]:
    """SHA-256 of every table in a DuckDB file, rows ordered by all columns."""
    con = duckdb.connect(str(path), read_only=True)
    try:
        names = [r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()]
        out = {}
        for t in sorted(names):
            df = con.execute(f"SELECT * FROM {t} ORDER BY ALL").df()
            h = hashlib.sha256(",".join(df.columns).encode())
            h.update(pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes())
            out[t] = h.hexdigest()
        return out
    finally:
        con.close()


# Live mode (D-179): who flew each sensor track the simulator sent. Appended by the simulator,
# keyed by the sensor's track id (writing a seed's flight again replaces its rows), read only by
# ``kairos_defense.eval`` (the reveal and ``live check``). ``write_all`` recreates the file, so
# ``make data`` also clears it.
LIVE_TRUTH_DDL = """CREATE TABLE IF NOT EXISTS live_truth (
  sensor_track_id VARCHAR PRIMARY KEY, actor_id VARCHAR, actor_type VARCHAR, nickname VARCHAR,
  scenario VARCHAR, seed BIGINT, base VARCHAR, flight INTEGER, drone INTEGER,
  launch_ts TIMESTAMP)"""
LIVE_TRUTH_COLUMNS = ["sensor_track_id", "actor_id", "actor_type", "nickname", "scenario", "seed",
                      "base", "flight", "drone", "launch_ts"]  # fmt: skip
LOCK_RETRIES = 40  # x 0.25 s: another process (the API's reveal) may hold the file briefly


def record_live_flights(app: AppConfig, rows: Sequence[dict]) -> int:
    """Append live flights' ground truth (one row per sensor track) to the truth file; returns
    the rows written. Retries while another process holds the file."""
    df = pd.DataFrame(list(rows), columns=LIVE_TRUTH_COLUMNS)
    path = Path(app.paths.truth)
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(LOCK_RETRIES):
        try:
            con = duckdb.connect(str(path))  # the one writer of truth (CLAUDE.md rule 2)
            break
        except duckdb.IOException:
            if attempt == LOCK_RETRIES - 1:
                raise
            time.sleep(0.25)
    try:
        con.execute(LIVE_TRUTH_DDL)
        if len(df):
            con.execute("DELETE FROM live_truth WHERE list_contains($ids, sensor_track_id)",
                        {"ids": df["sensor_track_id"].tolist()})  # fmt: skip
            con.register("df_in", df)
            con.execute("INSERT INTO live_truth SELECT * FROM df_in")
            con.unregister("df_in")
    finally:
        con.close()
    log.info("recorded %d live flight row(s) in %s", len(df), path)
    return len(df)
