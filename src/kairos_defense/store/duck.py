"""DuckDB adapter for the ``TrackStore`` port (SPEC §4.1) and the §11 context joins.

Every connection goes through ``connect_app_db``, so this adapter can never open ground truth.
Besides the port, the adapter offers the bulk queries the index build needs: the track list, RF and
Remote ID association for every track at once (§11.2, D-048), and writing the §7.2 derived tables.
The association queries take an optional ``until`` bound so a live (partial) track's sensor context
uses only what was heard up to the replay time (D-071, D-072).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from kairos_defense.config import AppConfig
from kairos_defense.features.signatures import SensorContext
from kairos_defense.store.ddl import DERIVED_COLUMNS, DERIVED_DDL
from kairos_defense.store.guard import connect_app_db

log = logging.getLogger(__name__)

RF_WINDOW_S = 30  # §11.2: RF detections within ±30 s of track points
RF_BEARING_GATE_DEG = 15.0  # §11.2: with concurrent drones, RF bearing within 15° of the track
RID_WINDOW_S = 5  # §9.4: Remote ID within ±5 s ...
RID_RADIUS_M = 100.0  # ... and 100 m of track points

_TRACK_FILTER = "WHERE ($ids IS NULL OR list_contains($ids, track_id))"
_UNTIL = "($until IS NULL OR {col} <= $until)"  # D-071: nothing heard or seen after the bound
_OFFSETS = "(VALUES (-1), (0), (1)) AS o(d)"  # neighbor time buckets for the window joins


def _bucket(col: str, width_s: int) -> str:
    """Integer time bucket of ``width_s`` seconds. Each track point is repeated for its own and
    both neighbor buckets, so a ±``width_s`` range join becomes an equi-join on (installation,
    bucket) followed by the exact filter; each true pair matches exactly one copy. (With the
    offset in the join condition instead, DuckDB 2.0 plans a plain range join: 100x slower.)"""
    return f"CAST(floor(epoch({col}) / {width_s}) AS BIGINT)"


class DuckTrackStore:
    """``TrackStore`` over ``data/kairos_defense.duckdb`` (or any app DuckDB file)."""

    def __init__(self, path: Path | str, app: AppConfig, *, read_only: bool = True) -> None:
        self.path = Path(path)
        self.con: duckdb.DuckDBPyConnection = connect_app_db(path, app, read_only=read_only)

    @classmethod
    def over(cls, con: duckdb.DuckDBPyConnection, path: Path | str) -> DuckTrackStore:
        """A store on an existing connection (for example a ``cursor()`` of a database another
        adapter opened through ``connect_app_db``), so a worker thread reads on its own
        connection (D-172). ``close`` closes that connection only."""
        store = cls.__new__(cls)
        store.path, store.con = Path(path), con
        return store

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> DuckTrackStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- TrackStore port -------------------------------------------------------------------
    def sql(self, query: str, params: dict | None = None) -> pd.DataFrame:
        return self.con.execute(query, params or {}).df()

    def track_points(self, track_id: str) -> pd.DataFrame:
        """Raw radar points of one track, ordered by ``ts``."""
        return self.sql(
            "SELECT * FROM track_points WHERE track_id = $t ORDER BY ts", {"t": track_id}
        )

    def features(self, track_id: str) -> pd.DataFrame:
        """1 Hz features of one history track (§9), ordered by ``t_s``; empty if not indexed."""
        return self.sql(
            "SELECT * FROM track_features WHERE track_id = $t ORDER BY t_s", {"t": track_id}
        )

    def features_many(self, track_ids: Sequence[str]) -> pd.DataFrame:
        """1 Hz features of many history tracks, ordered by ``track_id`` then ``t_s`` (D-072)."""
        return self.sql(
            "SELECT * FROM track_features WHERE list_contains($ids, track_id) "
            "ORDER BY track_id, t_s",
            {"ids": list(track_ids)},
        )

    def sensor_context_until(self, track_id: str, until: datetime) -> dict:
        """RF family, Remote ID serials and operator position of one track, from track points,
        detections and concurrent tracks up to ``until`` only (§10.5 partial signatures, D-071).
        Keys: ``rf_family`` (``"unknown"`` if none), ``rid_serials`` (tuple, most frequent first),
        ``rid_operator_xy`` (region meters or None)."""
        ctx = self.sensor_context([track_id], until=until).get(track_id, SensorContext())
        return {"rf_family": ctx.rf_family, "rid_serials": ctx.rid_serials,
                "rid_operator_xy": ctx.rid_operator_xy}  # fmt: skip

    def signature(self, track_id: str) -> dict:
        df = self.sql("SELECT * FROM track_signatures WHERE track_id = $t", {"t": track_id})
        if len(df) != 1:
            raise KeyError(f"no signature for track {track_id!r}")
        return df.iloc[0].to_dict()

    def tracks_before(self, ts: datetime, exclude_incident: str | None = None) -> pd.DataFrame:
        """§11.3: signatures of tracks that started strictly before ``ts`` (no look-ahead)."""
        return self.sql(
            "SELECT * FROM track_signatures WHERE start_ts < $t "
            "AND ($x IS NULL OR incident_id <> $x) ORDER BY start_ts, track_id",
            {"t": ts, "x": exclude_incident},
        )

    def context_asof(self, track_id: str) -> pd.DataFrame:
        """§11.1: per second of a history track, the latest weather at or before it and the base
        events active then (comma-separated kinds, NULL if none)."""
        return self.sql(
            """
            WITH f AS (SELECT * FROM track_features WHERE track_id = $t),
            ev AS (
              SELECT f.t_s, string_agg(DISTINCT e.kind, ',' ORDER BY e.kind) AS base_events
              FROM f JOIN base_events e
                ON e.installation_id = f.installation_id AND f.ts BETWEEN e.start_ts AND e.end_ts
              GROUP BY f.t_s)
            SELECT f.track_id, f.t_s, f.ts, f.speed_ms, w.ts AS weather_ts, w.wind_ms,
                   w.wind_dir_deg, w.visibility_km, ev.base_events
            FROM f JOIN installations i USING (installation_id)
            ASOF LEFT JOIN weather w ON i.region_id = w.region_id AND f.ts >= w.ts
            LEFT JOIN ev USING (t_s)
            ORDER BY f.ts
            """,
            {"t": track_id},
        )

    # --- §11 extras --------------------------------------------------------------------------
    def base_events_during(self, track_id: str) -> pd.DataFrame:
        """§11.1: base events overlapping a history track's span."""
        return self.sql(
            """SELECT e.kind, e.label, e.start_ts, e.end_ts
               FROM track_signatures s JOIN base_events e
                 ON e.installation_id = s.installation_id
                AND e.start_ts <= s.end_ts AND e.end_ts >= s.start_ts
               WHERE s.track_id = $t ORDER BY e.start_ts, e.kind""",
            {"t": track_id},
        )

    def tracks(self) -> pd.DataFrame:
        """One row per track: ids, incident ``status``, point count, first and last point time."""
        return self.sql(
            """SELECT p.track_id, p.incident_id, p.installation_id, p.region_id, i.status,
                      count(*) AS n_points, min(p.ts) AS start_ts, max(p.ts) AS end_ts
               FROM track_points p JOIN incidents i USING (incident_id)
               GROUP BY ALL ORDER BY p.track_id"""
        )

    def rf_association(
        self, track_ids: Sequence[str] | None = None, until: datetime | None = None
    ) -> pd.DataFrame:
        """§11.2 for many tracks: ``track_id, protocol_family, n`` (most detections first).

        An RF detection belongs to a track if it is within ±30 s of one of its points. When another
        track at the same installation overlaps in time (±60 s), the detection's bearing must also
        be within 15° of the bearing from the RF sensor to the track point nearest in time (D-048).
        ``until``: only points, detections and concurrent spans at or before it count (D-071).
        """
        return self.sql(
            f"""
            WITH pts AS (SELECT track_id, installation_id, ts, x_m, y_m,
                                {_bucket("ts", RF_WINDOW_S)} + o.d AS b
                         FROM track_points CROSS JOIN {_OFFSETS} {_TRACK_FILTER}
                          AND {_UNTIL.format(col="ts")}),
            spans AS (SELECT track_id, installation_id, min(ts) AS t0, max(ts) AS t1
                      FROM track_points WHERE {_UNTIL.format(col="ts")} GROUP BY ALL),
            conc AS (
              SELECT a.track_id, count(b.track_id) > 0 AS concurrent
              FROM spans a LEFT JOIN spans b
                ON b.installation_id = a.installation_id AND b.track_id <> a.track_id
               AND b.t0 <= a.t1 + INTERVAL {2 * RF_WINDOW_S} SECOND
               AND b.t1 >= a.t0 - INTERVAL {2 * RF_WINDOW_S} SECOND
              GROUP BY a.track_id),
            rf AS (
              SELECT row_number() OVER (ORDER BY r.sensor_id, r.ts, r.protocol_family,
                                        r.bearing_deg) AS rf_id,
                     r.installation_id, r.ts, r.protocol_family, r.bearing_deg,
                     s.x_m AS sx, s.y_m AS sy, {_bucket("r.ts", RF_WINDOW_S)} AS b
              FROM rf_detections r JOIN sensors s USING (sensor_id)
              WHERE {_UNTIL.format(col="r.ts")}),
            near AS (
              SELECT p.track_id, r.rf_id, any_value(r.protocol_family) AS fam,
                     any_value(r.bearing_deg) AS brg, any_value(r.sx) AS sx, any_value(r.sy) AS sy,
                     arg_min(p.x_m, abs(epoch_ms(p.ts) - epoch_ms(r.ts)) * 2
                                    + (p.ts > r.ts)::INTEGER) AS px,
                     arg_min(p.y_m, abs(epoch_ms(p.ts) - epoch_ms(r.ts)) * 2
                                    + (p.ts > r.ts)::INTEGER) AS py
              FROM pts p JOIN rf r
                ON r.installation_id = p.installation_id AND r.b = p.b
               AND r.ts BETWEEN p.ts - INTERVAL {RF_WINDOW_S} SECOND
                            AND p.ts + INTERVAL {RF_WINDOW_S} SECOND
              GROUP BY p.track_id, r.rf_id)
            SELECT n.track_id, n.fam AS protocol_family, count(*) AS n
            FROM near n JOIN conc c USING (track_id)
            WHERE NOT c.concurrent
               OR abs((degrees(atan2(n.px - n.sx, n.py - n.sy)) - n.brg + 540) % 360 - 180)
                  <= {RF_BEARING_GATE_DEG}
            GROUP BY ALL ORDER BY n.track_id, n DESC, protocol_family
            """,
            {"ids": None if track_ids is None else list(track_ids), "until": until},
        )

    def rid_association(
        self, track_ids: Sequence[str] | None = None, until: datetime | None = None
    ) -> pd.DataFrame:
        """§9.4 for many tracks: ``track_id, serial, n, op_x_m, op_y_m`` for Remote ID broadcasts
        within ±5 s and 100 m of a track point (most matches first; operator = median).
        ``until``: only points and broadcasts at or before it count (D-071)."""
        return self.sql(
            f"""
            WITH pts AS (SELECT track_id, installation_id, ts, x_m, y_m,
                                {_bucket("ts", RID_WINDOW_S)} + o.d AS b
                         FROM track_points CROSS JOIN {_OFFSETS} {_TRACK_FILTER}
                          AND {_UNTIL.format(col="ts")}),
            rid AS (SELECT *, {_bucket("ts", RID_WINDOW_S)} AS b FROM remote_id
                    WHERE {_UNTIL.format(col="ts")})
            SELECT p.track_id, r.serial, count(*) AS n,
                   median(r.op_x_m) AS op_x_m, median(r.op_y_m) AS op_y_m
            FROM pts p JOIN rid r
              ON r.installation_id = p.installation_id AND r.b = p.b
             AND r.ts BETWEEN p.ts - INTERVAL {RID_WINDOW_S} SECOND
                          AND p.ts + INTERVAL {RID_WINDOW_S} SECOND
            WHERE (r.drone_x_m - p.x_m) * (r.drone_x_m - p.x_m)
                + (r.drone_y_m - p.y_m) * (r.drone_y_m - p.y_m) <= {RID_RADIUS_M**2}
            GROUP BY ALL ORDER BY p.track_id, n DESC, r.serial
            """,
            {"ids": None if track_ids is None else list(track_ids), "until": until},
        )

    def sensor_context(
        self, track_ids: Sequence[str] | None = None, until: datetime | None = None
    ) -> dict[str, SensorContext]:
        """RF family, Remote ID serials and operator position per track (tracks with neither are
        absent: use ``SensorContext()``). ``until`` bounds everything heard or seen (D-071)."""
        rf = self.rf_association(track_ids, until)
        rid = self.rid_association(track_ids, until)
        fam = rf.groupby("track_id", sort=False)["protocol_family"].first().to_dict()
        out: dict[str, SensorContext] = {}
        for tid in set(fam) | set(rid["track_id"]):
            rows = rid[rid["track_id"] == tid]
            op = None
            if len(rows):
                top = rows.iloc[0]
                op = (float(top.op_x_m), float(top.op_y_m))
            out[tid] = SensorContext(
                rf_family=fam.get(tid, "unknown"),
                rid_serials=tuple(rows["serial"]),
                rid_operator_xy=op,
            )
        return out

    # --- writes (index build) ----------------------------------------------------------------
    def write_table(self, name: str, df: pd.DataFrame) -> int:
        """Drop and recreate one §7.2 derived table from ``df``; returns the row count."""
        if name not in DERIVED_DDL:
            raise ValueError(f"not a derived table: {name!r}")
        cols = DERIVED_COLUMNS[name]
        if list(df.columns) != cols:
            raise ValueError(f"{name}: columns {list(df.columns)} do not match the DDL {cols}")
        self.con.execute(f"DROP TABLE IF EXISTS {name}")
        self.con.execute(DERIVED_DDL[name])
        if len(df):
            self.con.register("df_in", df)
            self.con.execute(f"INSERT INTO {name} SELECT * FROM df_in")
            self.con.unregister("df_in")
        log.info("wrote %s (%d rows)", name, len(df))
        return len(df)
