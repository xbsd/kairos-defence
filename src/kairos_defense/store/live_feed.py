"""DuckDB adapter for the live-mode feed (``paths.live_mode``/``feed.duckdb``, D-172).

Everything live mode writes lives here, apart from the history, so ``live reset`` can remove it
all and the 18-month history, the evaluation and the replay are never written:

- ``live_points``, ``live_rf``, ``live_rid``: the ingested detections, with the columns of
  ``track_points``, ``rf_detections`` and ``remote_id`` (the §16.2 names the Recorder shows), and
  views with the source names over them plus a copy of ``sensors``, so the ``DuckTrackStore`` SQL
  (RF and Remote ID association up to ``until``, §11.2, D-071) runs unchanged on live rows;
- ``live_incidents`` (the ``incidents`` columns plus ``state`` and ``source = 'live'``) and an
  ``incidents`` view; ``live_tracks`` (the app's track id and the sensor's own track id);
- ``track_features`` and ``track_signatures`` of learned (closed) live tracks (D-176);
- ``live_results``: the matches each rerun showed (read by ``eval.reveal`` and ``live check``).

``DuckFeedStore`` is a ``DuckTrackStore`` over that file (the ``TrackStore`` port for learned live
history) with the ``LiveFeed`` write side. One connection behind an ``RLock``; ``reader()`` gives a
store on a cursor of the same database for the live worker thread. Truth is refused by
``connect_app_db``.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from kairos_defense.config import AppConfig
from kairos_defense.ports import IngestStat
from kairos_defense.store.ddl import (
    DERIVED_COLUMNS,
    DERIVED_DDL,
    LIVE_COLUMNS,
    LIVE_DDL,
    LIVE_SOURCES,
    RAW_COLUMNS,
    RAW_DDL,
)
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.guard import connect_app_db
from kairos_defense.store.live_duck import append_rows

log = logging.getLogger(__name__)

FEED_FILE = "feed.duckdb"
VECTORS_DIR = "vectors"
INCIDENT_COLUMNS = [*RAW_COLUMNS["incidents"], "state", "source"]
TRACK_COLUMNS = ["track_id", "incident_id", "installation_id", "region_id", "sensor_track_id",
                 "start_ts", "end_ts", "n_points"]  # fmt: skip
RESULT_COLUMNS = ["incident_id", "track_id", "t_s", "kind", "computed_ts", "model_version",
                  "elapsed_ms", "matches"]  # fmt: skip
STATES = ("open", "closing", "closed")

_DDL = {
    "live_incidents": """CREATE TABLE IF NOT EXISTS live_incidents (
  incident_id VARCHAR PRIMARY KEY, installation_id VARCHAR, region_id VARCHAR,
  start_ts TIMESTAMP, end_ts TIMESTAMP, n_tracks INTEGER, is_swarm BOOLEAN, status VARCHAR,
  state VARCHAR, source VARCHAR)""",
    "live_tracks": """CREATE TABLE IF NOT EXISTS live_tracks (
  track_id VARCHAR PRIMARY KEY, incident_id VARCHAR, installation_id VARCHAR, region_id VARCHAR,
  sensor_track_id VARCHAR, start_ts TIMESTAMP, end_ts TIMESTAMP, n_points INTEGER)""",
    "live_results": """CREATE TABLE IF NOT EXISTS live_results (
  incident_id VARCHAR, track_id VARCHAR, t_s INTEGER, kind VARCHAR, computed_ts TIMESTAMP,
  model_version VARCHAR, elapsed_ms DOUBLE, matches JSON)""",
}
# every table ``reset`` empties (``sensors`` is a copy of the history's and stays)
RESET_TABLES = (*LIVE_COLUMNS, "live_incidents", "live_tracks", "track_features",
                "track_signatures", "live_results")  # fmt: skip


def _if_not_exists(ddl: str) -> str:
    return ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)


class DuckFeedStore(DuckTrackStore):
    """The live-mode feed database. ``sensors``: the history's ``sensors`` rows (copied in so the
    association SQL can join them); None keeps what the file has."""

    def __init__(self, folder: Path | str, app: AppConfig,
                 sensors: pd.DataFrame | None = None) -> None:  # fmt: skip
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / FEED_FILE
        self.con = connect_app_db(self.path, app)
        self.lock = threading.RLock()
        with self.lock:
            for ddl in LIVE_DDL.values():
                self.con.execute(ddl)
            for live, src in LIVE_SOURCES.items():
                self.con.execute(f"CREATE OR REPLACE VIEW {src} AS SELECT * FROM {live}")
            self.con.execute(_if_not_exists(RAW_DDL["sensors"]))
            for ddl in _DDL.values():
                self.con.execute(ddl)
            cols = ", ".join(RAW_COLUMNS["incidents"])
            self.con.execute(f"CREATE OR REPLACE VIEW incidents AS SELECT {cols} "
                             "FROM live_incidents")  # fmt: skip
            for name in ("track_features", "track_signatures"):
                self.con.execute(_if_not_exists(DERIVED_DDL[name]))
            if sensors is not None:
                self.con.execute("DELETE FROM sensors")
                if len(sensors):
                    self.con.register("sensors_in", sensors[RAW_COLUMNS["sensors"]])
                    self.con.execute("INSERT INTO sensors SELECT * FROM sensors_in")
                    self.con.unregister("sensors_in")

    # --- reads (every inherited TrackStore method goes through ``sql``) ---------------------
    def sql(self, query: str, params: dict | None = None) -> pd.DataFrame:
        with self.lock:
            return self.con.execute(query, params or {}).df()

    def reader(self) -> DuckTrackStore:
        """A ``TrackStore`` on its own cursor of this database, for one other thread."""
        with self.lock:
            return DuckTrackStore.over(self.con.cursor(), self.path)

    def count(self, table: str) -> int:
        if table not in RESET_TABLES:
            raise ValueError(f"not a live-mode table: {table!r}")
        return int(self.sql(f"SELECT count(*) AS n FROM {table}")["n"].iloc[0])

    def counts(self) -> dict[str, int]:
        return {t: self.count(t) for t in RESET_TABLES}

    def incidents(self) -> pd.DataFrame:
        return self.sql("SELECT * FROM live_incidents ORDER BY start_ts, incident_id")

    def incident(self, incident_id: str) -> dict | None:
        df = self.sql("SELECT * FROM live_incidents WHERE incident_id = $i", {"i": incident_id})
        return df.iloc[0].to_dict() if len(df) else None

    def live_tracks(self, incident_id: str | None = None) -> pd.DataFrame:
        """``live_tracks`` rows (one incident's, or all), by start time."""
        return self.sql("SELECT * FROM live_tracks WHERE ($i IS NULL OR incident_id = $i) "
                        "ORDER BY start_ts, track_id", {"i": incident_id})  # fmt: skip

    def results(self, incident_id: str) -> list[dict]:
        """The reruns of one incident in ``t_s`` order, ``matches`` parsed."""
        df = self.sql("SELECT * FROM live_results WHERE incident_id = $i ORDER BY t_s, kind",
                      {"i": incident_id})  # fmt: skip
        out = df.to_dict("records")
        for r in out:
            r["matches"] = json.loads(r["matches"]) if isinstance(r["matches"], str) else []
        return out

    # --- writes (the LiveFeed port) ----------------------------------------------------------
    def append(self, table: str, rows: Sequence[dict]) -> IngestStat:
        """Detections into ``live_points``, ``live_rf`` or ``live_rid``; one timed insert."""
        if table not in LIVE_COLUMNS:
            raise ValueError(f"not a live detection table: {table!r}")
        with self.lock:
            return append_rows(self.con, table, LIVE_COLUMNS[table], rows)

    def put_incident(self, row: dict) -> None:
        """Insert or replace one ``live_incidents`` row (app state, not the ledger)."""
        if row.get("state") not in STATES:
            raise ValueError(f"bad incident state {row.get('state')!r}")
        df = pd.DataFrame([{**row, "status": "live", "source": "live"}], columns=INCIDENT_COLUMNS)
        with self.lock:
            self.con.execute("DELETE FROM live_incidents WHERE incident_id = $i",
                             {"i": row["incident_id"]})  # fmt: skip
            self.con.register("inc_in", df)
            self.con.execute("INSERT INTO live_incidents SELECT * FROM inc_in")
            self.con.unregister("inc_in")

    def put_track(self, row: dict) -> None:
        df = pd.DataFrame([row], columns=TRACK_COLUMNS)
        with self.lock:
            self.con.execute("DELETE FROM live_tracks WHERE track_id = $t", {"t": row["track_id"]})
            self.con.register("trk_in", df)
            self.con.execute("INSERT INTO live_tracks SELECT * FROM trk_in")
            self.con.unregister("trk_in")

    def learn(self, features: pd.DataFrame, signatures: pd.DataFrame) -> int:
        """Add learned tracks' ``track_features`` and ``track_signatures`` rows (D-176)."""
        for name, df in (("track_features", features), ("track_signatures", signatures)):
            if list(df.columns) != DERIVED_COLUMNS[name]:
                raise ValueError(f"{name}: columns {list(df.columns)} do not match the DDL")
        with self.lock:
            ids = list(signatures["track_id"].astype(str))
            for name, df in (("track_features", features), ("track_signatures", signatures)):
                self.con.execute(f"DELETE FROM {name} WHERE list_contains($ids, track_id)",
                                 {"ids": ids})  # fmt: skip
                if len(df):
                    self.con.register("df_in", df)
                    self.con.execute(f"INSERT INTO {name} SELECT * FROM df_in")
                    self.con.unregister("df_in")
        return len(signatures)

    def add_result(self, row: dict) -> None:
        doc = {**row, "matches": json.dumps(row.get("matches", []), allow_nan=False)}
        df = pd.DataFrame([doc], columns=RESULT_COLUMNS)
        with self.lock:
            self.con.register("res_in", df)
            self.con.execute("INSERT INTO live_results SELECT * FROM res_in")
            self.con.unregister("res_in")

    def reset(self) -> dict[str, int]:
        """Empty every live-mode table; returns the rows removed per table."""
        out = {}
        with self.lock:
            for table in RESET_TABLES:
                out[table] = int(self.con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
                self.con.execute(f"DELETE FROM {table}")  # live-mode state, never the ledger
            self.con.execute("CHECKPOINT")
        log.info("reset live-mode tables %s", out)
        return out

    def close(self) -> None:
        with self.lock:
            self.con.close()
