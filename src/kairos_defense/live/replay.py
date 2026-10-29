"""The replay engine (SPEC §16.1, D-118): a live incident's detections on a replay clock.

``LiveIncident`` holds one live incident's radar points, RF detections and Remote ID messages
(the installation's, inside the incident's window), each with ``t_s``: float seconds since
``incidents.start_ts`` (T+0, the first detection, D-039). ``ReplayEngine`` is the clock: it
advances by ``speed × wall seconds`` while playing, from an injectable monotonic time source, and
pauses itself at ``duration_s``. Everything goes through the ``TrackStore`` port.
"""

from __future__ import annotations

import time
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from kairos_defense.ports import TrackStore

SPEEDS = (1.0, 2.0, 5.0)  # §6.1
KIND_ORDER = {"point": 0, "rf": 1, "rid": 2}
TABLES = {"point": "live_points", "rf": "live_rf", "rid": "live_rid"}


def _naive(ts) -> datetime:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t.to_pydatetime()


def iso_z(t: datetime) -> str:
    """ISO 8601 UTC with ``Z`` and milliseconds."""
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def _f(v) -> float | None:
    return None if v is None or not np.isfinite(v) else round(float(v), 3)


@dataclass(frozen=True)
class LiveIncident:
    """One live incident, loaded once. Frames hold the source table's columns plus ``t_s``."""

    incident_id: str
    installation_id: str
    region_id: str
    start_ts: datetime  # naive UTC, T+0
    end_ts: datetime
    n_tracks: int
    is_swarm: bool
    utc_offset_hours: int
    tracks: tuple[str, ...]
    points: pd.DataFrame
    rf: pd.DataFrame
    rid: pd.DataFrame
    messages: tuple[dict, ...] = field(repr=False, default=())  # every detection, in order
    times: tuple[float, ...] = field(repr=False, default=())  # their t_s (sorted)

    @property
    def duration_s(self) -> float:
        return (self.end_ts - self.start_ts).total_seconds()

    def ts_at(self, t_s: float) -> datetime:
        return self.start_ts + timedelta(seconds=float(t_s))

    def detections(self, t0: float, t1: float) -> list[dict]:
        """Detection messages with ``t0 < t_s <= t1`` (``t0 < 0`` includes T+0), in order: by
        ``t_s``, then point, rf, rid, then sensor and track."""
        return list(self.messages[bisect_right(self.times, t0) : bisect_right(self.times, t1)])

    def rows(self, t0: float, t1: float) -> dict[str, list[dict]]:
        """The source rows behind ``detections(t0, t1)``, per live table (§16.2)."""
        out: dict[str, list[dict]] = {}
        for kind, df in (("point", self.points), ("rf", self.rf), ("rid", self.rid)):
            t = df["t_s"].to_numpy()
            sel = df[(t > t0) & (t <= t1)].drop(columns="t_s")
            if len(sel):
                out[TABLES[kind]] = sel.to_dict("records")
        return out


def _messages(inc_id: str, points: pd.DataFrame, rf: pd.DataFrame, rid: pd.DataFrame) -> list:
    msgs = []
    for r in points.itertuples(index=False):
        msgs.append({"type": "point", "incident_id": inc_id, "track_id": r.track_id,
                     "sensor_id": r.sensor_id, "t_s": r.t_s, "x_m": _f(r.x_m), "y_m": _f(r.y_m),
                     "alt_m": _f(r.alt_m), "quality": _f(r.quality)})  # fmt: skip
    for r in rf.itertuples(index=False):
        msgs.append({"type": "rf", "sensor_id": r.sensor_id, "t_s": r.t_s, "band": r.band,
                     "bearing_deg": _f(r.bearing_deg), "protocol_family": r.protocol_family,
                     "snr_db": _f(r.snr_db)})  # fmt: skip
    for r in rid.itertuples(index=False):
        msgs.append({"type": "rid", "serial": r.serial, "t_s": r.t_s,
                     "drone_x_m": _f(r.drone_x_m), "drone_y_m": _f(r.drone_y_m),
                     "op_x_m": _f(r.op_x_m), "op_y_m": _f(r.op_y_m)})  # fmt: skip
    msgs.sort(key=lambda m: (m["t_s"], KIND_ORDER[m["type"]], m.get("sensor_id") or "",
                             m.get("track_id") or m.get("serial") or ""))  # fmt: skip
    return msgs


def live_incident_ids(store: TrackStore) -> list[str]:
    """Live incidents, single-track ones first."""
    df = store.sql("SELECT incident_id FROM incidents WHERE status = 'live' "
                   "ORDER BY is_swarm, start_ts, incident_id")  # fmt: skip
    return df["incident_id"].tolist()


def load_incident(store: TrackStore, incident_id: str) -> LiveIncident:
    """Load a live incident (``status = 'live'``); raises ``KeyError`` for any other id."""
    inc = store.sql("SELECT i.*, g.utc_offset_hours FROM incidents i JOIN regions g "
                    "USING (region_id) WHERE incident_id = $i AND status = 'live'",
                    {"i": incident_id})  # fmt: skip
    if inc.empty:
        raise KeyError(f"no live incident {incident_id!r}")
    row = inc.iloc[0]
    start, end = _naive(row["start_ts"]), _naive(row["end_ts"])
    window = {"b": str(row["installation_id"]), "t0": start, "t1": end}
    points = store.sql("SELECT * FROM track_points WHERE incident_id = $i ORDER BY ts, track_id",
                       {"i": incident_id})  # fmt: skip
    rf = store.sql("SELECT * FROM rf_detections WHERE installation_id = $b AND ts BETWEEN $t0 "
                   "AND $t1 ORDER BY ts, sensor_id", window)  # fmt: skip
    rid = store.sql("SELECT * FROM remote_id WHERE installation_id = $b AND ts BETWEEN $t0 "
                    "AND $t1 ORDER BY ts, serial", window)  # fmt: skip
    for df in (points, rf, rid):
        ts = pd.to_datetime(df["ts"])
        df["t_s"] = ((ts - pd.Timestamp(start)).dt.total_seconds()).round(3)
    msgs = _messages(incident_id, points, rf, rid)
    return LiveIncident(incident_id, str(row["installation_id"]), str(row["region_id"]), start,
                        end, int(row["n_tracks"]), bool(row["is_swarm"]),
                        int(row["utc_offset_hours"]), tuple(sorted(points["track_id"].unique())),
                        points, rf, rid, tuple(msgs), tuple(m["t_s"] for m in msgs))  # fmt: skip


class ReplayEngine:
    """The replay clock of one incident (§16.1). ``now`` is a monotonic time source in seconds."""

    def __init__(self, incident: LiveIncident, speed: float = 1.0,
                 now: Callable[[], float] = time.monotonic) -> None:  # fmt: skip
        self.incident, self._now = incident, now
        self.speed = self._check(speed)
        self._t, self._wall, self.playing = 0.0, now(), False

    @staticmethod
    def _check(speed: float) -> float:
        if float(speed) not in SPEEDS:
            raise ValueError(f"speed must be 1, 2 or 5, not {speed!r}")
        return float(speed)

    @property
    def duration_s(self) -> float:
        return self.incident.duration_s

    @property
    def elapsed_s(self) -> float:
        """Replay seconds since T+0; pauses itself at the end."""
        if not self.playing:
            return self._t
        t = self._t + self.speed * (self._now() - self._wall)
        if t >= self.duration_s:
            self._t, self.playing = self.duration_s, False
            return self._t
        return t

    def _anchor(self) -> None:
        self._t, self._wall = self.elapsed_s, self._now()

    def play(self) -> None:
        if self.elapsed_s >= self.duration_s:
            return
        self._anchor()
        self.playing = True

    def pause(self) -> None:
        self._anchor()
        self.playing = False

    def seek(self, t_s: float) -> float:
        self._t = min(max(float(t_s), 0.0), self.duration_s)
        self._wall = self._now()
        return self._t

    def reset(self) -> None:
        self.seek(0.0)
        self.playing = False

    def set_speed(self, speed: float) -> None:
        v = self._check(speed)
        self._anchor()
        self.speed = v

    def visible_points(self) -> pd.DataFrame:
        pts = self.incident.points
        return pts[pts["t_s"] <= self.elapsed_s]
