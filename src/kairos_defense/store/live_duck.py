"""DuckDB adapter for the ``LiveSink`` port (SPEC §16.2, D-103, D-104): ``data/live.duckdb``.

A replay appends each batch of newly visible detections to ``live_points``, ``live_rf`` or
``live_rid`` (the columns of ``track_points``, ``rf_detections`` and ``remote_id``) and gets back
the measured write: rows, running total, milliseconds and the statement's shape. ``reset`` empties
only these scratch tables, in their own file: the ledger lives elsewhere and is never touched.
The connection goes through ``connect_app_db``, so it can never open truth.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from kairos_defense.config import AppConfig
from kairos_defense.ports import IngestStat
from kairos_defense.store.ddl import LIVE_COLUMNS, LIVE_DDL
from kairos_defense.store.guard import connect_app_db

log = logging.getLogger(__name__)


def statement(table: str, rows: int) -> str:
    """The shape of a batch insert, e.g. ``INSERT INTO live_points … 3 rows``."""
    return f"INSERT INTO {table} … {rows} row{'' if rows == 1 else 's'}"


class DuckLiveSink:
    """``LiveSink`` over one DuckDB file (writable; tables created on open)."""

    def __init__(self, path: Path | str, app: AppConfig) -> None:
        self.path = Path(path)
        self.con = connect_app_db(self.path, app)
        self._lock = threading.Lock()
        for ddl in LIVE_DDL.values():
            self.con.execute(ddl)

    def close(self) -> None:
        with self._lock:
            self.con.close()

    def __enter__(self) -> DuckLiveSink:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _table(self, table: str) -> list[str]:
        if table not in LIVE_COLUMNS:
            raise ValueError(f"not a live table: {table!r}")
        return LIVE_COLUMNS[table]

    def count(self, table: str) -> int:
        self._table(table)
        with self._lock:
            return int(self.con.execute(f"SELECT count(*) FROM {table}").fetchall()[0][0])

    def append(self, table: str, rows: Sequence[dict]) -> IngestStat:
        """Insert ``rows`` (dicts with exactly the table's columns; times naive UTC) in one
        statement; the returned ``write_ms`` times that statement."""
        cols = self._table(table)
        with self._lock:
            ms = 0.0
            if rows:
                df = pd.DataFrame.from_records(list(rows), columns=cols)
                self.con.register("rows_in", df)
                t0 = time.perf_counter()
                self.con.execute(
                    f"INSERT INTO {table} SELECT {', '.join(cols)} FROM rows_in"
                ).fetchall()
                ms = (time.perf_counter() - t0) * 1e3
                self.con.unregister("rows_in")
            total = int(self.con.execute(f"SELECT count(*) FROM {table}").fetchall()[0][0])
        return IngestStat(table, len(rows), total, ms, statement(table, len(rows)))

    def reset(self) -> dict[str, int]:
        """Empty every ``live_*`` table; returns the rows removed per table."""
        out = {}
        with self._lock:
            for table in LIVE_COLUMNS:
                out[table] = int(self.con.execute(f"SELECT count(*) FROM {table}").fetchall()[0][0])
                self.con.execute(f"DELETE FROM {table}").fetchall()  # scratch, not the ledger
            self.con.execute("CHECKPOINT")
        log.info("reset live tables %s", out)
        return out
