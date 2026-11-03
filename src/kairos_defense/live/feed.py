"""The live hub (D-172 to D-175, D-184): what the app does with an incoming sensor feed.

``LiveHub.ingest`` takes schema-checked ingest messages (``api/schemas_ingest.py``; times naive
UTC), checks what only the app can (installation, sensor, after the history, not too late),
groups radar points into live incidents (``IncidentTracker``), writes every detection to the
live-mode store in one timed batch per table, streams what happened to the installation's
subscribers, and queues work for the live worker (``runner.LiveWorker``): a rerun each
``rerun_every_s`` of feed time from ``min_track_s``, with the points received up to that second
(rule 3), and a close task once an incident has been idle ``idle_close_s``. The hub never sees
who flew: messages carry none of it, by contract.

Thread-safety: one ``RLock`` around the hub's state; the worker calls ``result`` and ``closed``
from its own thread. Stream messages go through one ``Broadcaster`` per installation (each live
WebSocket drains its own queue) and a 120 s catch-up buffer for new subscribers.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from kairos_defense.config import ScoringConfig
from kairos_defense.features.channels import SiteGeometry, track_features
from kairos_defense.features.resample import epoch_ms
from kairos_defense.live.broadcast import Broadcaster
from kairos_defense.live.incidents import IncidentTracker, LiveIncidentState
from kairos_defense.live.loop import FEATURE_KEYS, _num
from kairos_defense.live.phase import flight_phase
from kairos_defense.live.replay import iso_z
from kairos_defense.ports import LiveFeed

CATCH_UP_S = 120.0
FEATURES_MIN_WALL_S = 0.2  # at most 5 features messages per wall second per incident
ACTIVE_WALL_S = 2.0  # the feed counts as live while a message arrived this recently
POINT_COLS = ["incident_id", "track_id", "installation_id", "region_id", "sensor_id", "ts", "x_m",
              "y_m", "alt_m", "quality"]  # fmt: skip


@dataclass(frozen=True)
class RerunTask:
    """Rerun ``t_s`` seconds after the incident's first point, on the points up to then."""

    meta: dict  # incident_id, installation_id, region_id, start_ts, n_tracks, is_swarm, tracks
    t_s: float
    points: pd.DataFrame  # every track's points with ts <= start + t_s


@dataclass(frozen=True)
class CloseTask:
    meta: dict
    points: pd.DataFrame  # every point of the incident


@dataclass
class _Inst:
    feed_ms: int | None = None
    heard_ms: int | None = None  # the last RF or Remote ID detection heard here
    rate: float = 1.0
    wall: float = 0.0  # wall time of the last message
    recent: deque = field(default_factory=deque)  # (ms, message) of the current incident
    results: list[dict] = field(default_factory=list)  # latest result messages
    trace: dict | None = None  # the latest matcher_trace message (the DTW workbench, D-188)


def _ms_to_dt(ms: int) -> datetime:
    return pd.Timestamp(int(ms), unit="ms").to_pydatetime()


class LiveHub:
    """``sites``: installation -> ``SiteGeometry``; ``sensors``: sensor id -> (installation,
    kind); ``history_end``: the newest end of any stored incident (naive UTC; live detections
    must come after it, rule 3); ``submit``: queues a task for the worker."""

    def __init__(self, scoring: ScoringConfig, sites: dict[str, SiteGeometry],
                 sensors: dict[str, tuple[str, str]], feed: LiveFeed, history_end: datetime, *,
                 submit: Callable[[object], None], used_ids: Sequence[str] = (),
                 matching: bool = True,
                 now: Callable[[], float] = time.monotonic) -> None:  # fmt: skip
        self.scoring, self.sites, self.sensors, self.feed = scoring, sites, sensors, feed
        self.history_end, self.submit, self.matching, self._now = history_end, submit, matching, now
        live = scoring.live
        self.lateness_ms = round(float(live.max_lateness_s) * 1000)
        self.tracker = IncidentTracker(
            scoring, {i: (s.region_id, s.utc_offset_hours) for i, s in sites.items()}, used_ids
        )
        self.lock = threading.RLock()
        self._inst: dict[str, _Inst] = defaultdict(_Inst)
        self._bus: dict[str, Broadcaster] = defaultdict(Broadcaster)
        self._points: dict[str, list[dict]] = defaultdict(list)  # track id -> rows
        self._snap_n: dict[str, int] = {}  # incident -> points in its last rerun
        self._feat: dict[str, tuple[int, float]] = {}  # incident -> (second, wall) last sent

    # --- checks -------------------------------------------------------------------------------
    def check(self, m: dict) -> str | None:
        """Why the app refuses one schema-valid message (None: accepted)."""
        inst = m["installation_id"]
        if inst not in self.sites:
            return f"unknown installation {inst!r}"
        kind = {"point": "radar", "rf": "rf"}.get(m["type"])
        if kind is not None:
            owner = self.sensors.get(m["sensor_id"])
            if owner != (inst, kind):
                return f"sensor {m['sensor_id']!r} is not the {kind} sensor of {inst}"
        if m["ts"] <= self.history_end:
            end = iso_z(self.history_end)
            return (
                f"timestamp {iso_z(m['ts'])} is not after the end of the history ({end}): "
                "live detections must be newer (rule 3)"
            )
        feed_ms = self._inst[inst].feed_ms
        if feed_ms is not None and epoch_ms(m["ts"]) < feed_ms - self.lateness_ms:
            late = (feed_ms - epoch_ms(m["ts"])) / 1000
            return f"late: {late:.1f} s behind the feed time at {inst}"
        return None

    # --- ingest -------------------------------------------------------------------------------
    def ingest(self, msgs: Sequence[dict]) -> dict:
        """Apply a batch in order; returns ``accepted`` (all), ``detections`` and ``rejected``
        (``[{index, reason}]``)."""
        rejected, rows, touched, accepted, det = [], defaultdict(list), [], 0, 0
        with self.lock:
            now = self._now()
            for i, m in enumerate(msgs):
                reason = self.check(m)
                if reason:
                    rejected.append({"index": i, "reason": reason})
                    continue
                inst, ms = m["installation_id"], epoch_ms(m["ts"])
                st = self._inst[inst]
                st.feed_ms = ms if st.feed_ms is None else max(st.feed_ms, ms)
                st.wall = now
                if inst not in touched:
                    touched.append(inst)
                accepted += 1
                if m["type"] == "heartbeat":
                    st.rate = float(m.get("rate") or 1.0)
                    continue
                det += 1
                if m["type"] != "point":
                    st.heard_ms = ms if st.heard_ms is None else max(st.heard_ms, ms)
                getattr(self, "_" + m["type"])(m, inst, ms, rows)
            for table, rs in rows.items():
                stat = self.feed.append(table, rs)
                for inst in dict.fromkeys(r["installation_id"] for r in rs):
                    self._emit(inst, {"type": "ingest", **stat.to_dict()}, keep=False)
            for inst in touched:
                self._advance(inst)
        return {"accepted": accepted, "detections": det, "rejected": rejected}

    def _point(self, m: dict, inst: str, ms: int, rows) -> None:
        trk, events = self.tracker.point(inst, m["sensor_track_id"], ms, m["x_m"], m["y_m"])
        inc = self.tracker.incidents[trk.incident_id]
        for ev, _ in events:
            if ev == "opened":
                self._opened(inc)
            self._persist(inc)
        if trk.n_points == 1:
            self.feed.put_track(self._track_row(trk, inc))
        row = {"incident_id": inc.incident_id, "track_id": trk.track_id, "installation_id": inst,
               "region_id": inc.region_id, "sensor_id": m["sensor_id"], "ts": m["ts"],
               "x_m": m["x_m"], "y_m": m["y_m"], "alt_m": m["alt_m"],
               "quality": m["quality"]}  # fmt: skip
        rows["live_points"].append(row)
        self._points[trk.track_id].append(row)
        self._emit(inst, {"type": "point", "incident_id": inc.incident_id,
                          "track_id": trk.track_id, "sensor_id": m["sensor_id"],
                          "t_s": inc.t_s(ms), "x_m": m["x_m"], "y_m": m["y_m"],
                          "alt_m": m["alt_m"], "quality": m["quality"]}, ms, inc)  # fmt: skip

    def _rf(self, m: dict, inst: str, ms: int, rows) -> None:
        rows["live_rf"].append({k: m[k] for k in ("installation_id", "sensor_id", "ts", "band",
                                                  "protocol_family", "bearing_deg",
                                                  "snr_db")})  # fmt: skip
        inc = self._streaming(inst)
        if inc is not None:
            self._emit(inst, {"type": "rf", "sensor_id": m["sensor_id"], "t_s": inc.t_s(ms),
                              "band": m["band"], "bearing_deg": m["bearing_deg"],
                              "protocol_family": m["protocol_family"],
                              "snr_db": m["snr_db"]}, ms, inc)  # fmt: skip

    def _rid(self, m: dict, inst: str, ms: int, rows) -> None:
        keys = ("installation_id", "ts", "serial", "drone_x_m", "drone_y_m", "op_x_m", "op_y_m")
        rows["live_rid"].append({k: m[k] for k in keys})
        inc = self._streaming(inst)
        if inc is not None:
            self._emit(inst, {"type": "rid", "serial": m["serial"], "t_s": inc.t_s(ms),
                              **{k: m[k] for k in keys[3:]}}, ms, inc)  # fmt: skip

    def _streaming(self, inst: str) -> LiveIncidentState | None:
        """The incident whose detections the installation's stream shows (open only)."""
        inc = self.tracker.current(inst)
        return inc if inc is not None and inc.state == "open" else None

    # --- incidents ------------------------------------------------------------------------------
    def meta(self, inc: LiveIncidentState) -> dict:
        return {"incident_id": inc.incident_id, "installation_id": inc.installation_id,
                "region_id": inc.region_id, "start_ts": _ms_to_dt(inc.start_ms),
                "n_tracks": len(inc.tracks), "is_swarm": inc.is_swarm,
                "tracks": list(inc.tracks)}  # fmt: skip

    def _track_row(self, trk, inc: LiveIncidentState, n: int | None = None) -> dict:
        return {"track_id": trk.track_id, "incident_id": inc.incident_id,
                "installation_id": trk.installation_id, "region_id": inc.region_id,
                "sensor_track_id": trk.sensor_track_id, "start_ts": _ms_to_dt(trk.first_ms),
                "end_ts": _ms_to_dt(trk.last_ms), "n_points": n or trk.n_points}  # fmt: skip

    def _persist(self, inc: LiveIncidentState) -> None:
        self.feed.put_incident({"incident_id": inc.incident_id,
                                "installation_id": inc.installation_id,
                                "region_id": inc.region_id, "start_ts": _ms_to_dt(inc.start_ms),
                                "end_ts": _ms_to_dt(inc.last_ms), "n_tracks": len(inc.tracks),
                                "is_swarm": inc.is_swarm, "state": inc.state})  # fmt: skip

    def _opened(self, inc: LiveIncidentState) -> None:
        st = self._inst[inc.installation_id]
        st.recent.clear()
        st.results = []
        self._emit(inc.installation_id, {"type": "incident_opened", "incident_id": inc.incident_id,
                                         "installation_id": inc.installation_id,
                                         "start_ts": iso_z(_ms_to_dt(inc.start_ms))},
                   keep=False)  # fmt: skip
        self._emit(inc.installation_id, self.hello(inc.installation_id), keep=False)

    def _snapshot(self, inc: LiveIncidentState, until_ms: int | None = None) -> pd.DataFrame:
        rows = [r for t in inc.tracks for r in self._points.get(t, ())
                if until_ms is None or epoch_ms(r["ts"]) <= until_ms]  # fmt: skip
        return pd.DataFrame(rows, columns=POINT_COLS)

    def _advance(self, inst: str) -> None:
        """Queue the reruns feed time has passed, then close idle incidents, then features."""
        st = self._inst[inst]
        if st.feed_ms is None:
            return
        for inc in self.tracker.open_incidents(inst):
            for t in self.tracker.due_reruns(inc, st.feed_ms):
                snap = self._snapshot(inc, inc.start_ms + round(t * 1000))
                if len(snap) == self._snap_n.get(inc.incident_id):
                    continue  # nothing new since the previous rerun: same result
                self._snap_n[inc.incident_id] = len(snap)
                self.submit(RerunTask(self.meta(inc), float(t), snap))
        for inc in self.tracker.idle(inst, st.feed_ms, st.heard_ms):
            self._persist(inc)
            self.submit(CloseTask(self.meta(inc), self._snapshot(inc)))
        self._features(inst)

    def _features(self, inst: str) -> None:
        inc = self._streaming(inst)
        st = self._inst[inst]
        if inc is None or st.feed_ms is None:
            return
        s = math.floor((st.feed_ms - inc.start_ms) / 1000)
        last_s, last_wall = self._feat.get(inc.incident_id, (0, -1e9))
        now = self._now()
        if s <= last_s or s < 1 or now - last_wall < FEATURES_MIN_WALL_S:
            return
        pts = [r for r in self._points[inc.tracks[0]]
               if epoch_ms(r["ts"]) <= inc.start_ms + s * 1000]  # fmt: skip
        try:
            f, target = track_features(pd.DataFrame(pts, columns=POINT_COLS), self.sites[inst],
                                       self.scoring)  # fmt: skip
        except ValueError:
            return
        self._feat[inc.incident_id] = (s, now)
        last = f.iloc[-1]
        self._emit(inst, {"type": "features", "t_s": float(s), "track_id": inc.tracks[0],
                          "target_asset_id": target.asset_id,
                          **{k: _num(last[k]) for k in FEATURE_KEYS},
                          "phase": flight_phase(f, target.kind)},
                   inc.start_ms + s * 1000, inc)  # fmt: skip

    def flush(self, installations: Sequence[str]) -> int:
        """The feed of these installations ended (its simulator exited): move their feed time
        past every open incident's idle limit so they close. Returns the incidents closed."""
        n = 0
        with self.lock:
            for inst in installations:
                st = self._inst[inst]
                for inc in self.tracker.open_incidents(inst):
                    last = max(inc.last_ms, st.heard_ms or 0)
                    st.feed_ms = max(st.feed_ms or 0, last + self.tracker.idle_ms + 1)
                    n += 1
                self._advance(inst)
        return n

    # --- from the worker ----------------------------------------------------------------------
    def result(self, incident_id: str, msgs: list[dict]) -> None:
        """A rerun's messages: stream them if the incident is the installation's current one
        (a backfilled rerun brings none)."""
        with self.lock:
            inc = self.tracker.incidents.get(incident_id)
            if inc is None:
                return  # reset meanwhile
            inc.reruns += 1
            if msgs and self.tracker.current(inc.installation_id) is inc:
                st = self._inst[inc.installation_id]
                st.results = list(msgs)
                st.trace = next((m for m in msgs if m["type"] == "matcher_trace"), st.trace)
                for m in msgs:
                    self._emit(inc.installation_id, m, keep=False)

    def closed(self, incident_id: str, summary: dict) -> None:
        with self.lock:
            inc = self.tracker.incidents.get(incident_id)
            if inc is None:
                return
            inc.state = "closed"
            self._persist(inc)
            for t in inc.tracks:
                trk = self.tracker.tracks[t]
                self.feed.put_track(self._track_row(trk, inc, len(self._points.pop(t, ()))))
            self._snap_n.pop(incident_id, None)
            self._feat.pop(incident_id, None)
            self._emit(inc.installation_id, {
                "type": "incident_closed", "incident_id": incident_id,
                "installation_id": inc.installation_id,
                "end_ts": iso_z(_ms_to_dt(inc.last_ms)),
                "duration_s": round((inc.last_ms - inc.start_ms) / 1000, 3),
                "n_tracks": len(inc.tracks), "is_swarm": inc.is_swarm, "reruns": inc.reruns,
                "learned_tracks": int(summary.get("learned_tracks", 0))}, keep=False)  # fmt: skip

    # --- the stream ---------------------------------------------------------------------------
    def _emit(self, inst: str, msg: dict, ms: int | None = None, inc=None, keep=True) -> None:
        self._bus[inst].publish([msg])
        if keep and inc is not None and ms is not None:
            st = self._inst[inst]
            st.recent.append((ms, msg))
            floor = (st.feed_ms or ms) - round(CATCH_UP_S * 1000)
            while st.recent and st.recent[0][0] < floor:
                st.recent.popleft()

    def subscribe(self, inst: str):
        return self._bus[inst].subscribe()

    def hello(self, inst: str) -> dict:
        with self.lock:
            site, st = self.sites[inst], self._inst[inst]
            inc = self.tracker.current(inst)
            start = inc.start_ms if inc else (st.feed_ms or epoch_ms(self.history_end))
            live = self.scoring.live
            return {"type": "hello", "incident_id": inc.incident_id if inc else "",
                    "installation_id": inst, "region_id": site.region_id,
                    "start_ts": iso_z(_ms_to_dt(start)),
                    "duration_s": 0.0,  # open-ended: a live incident has no known end
                    "speed": st.rate, "playing": self._active(st),
                    "tracks": list(inc.tracks) if inc else [],
                    "is_swarm": bool(inc and inc.is_swarm), "matching": self.matching,
                    "min_track_s": float(live.min_track_s),
                    "rerun_every_s": float(live.rerun_every_s),
                    "utc_offset_hours": site.utc_offset_hours}  # fmt: skip

    def _active(self, st: _Inst) -> bool:
        return st.feed_ms is not None and self._now() - st.wall < ACTIVE_WALL_S

    def clock(self, inst: str) -> dict | None:
        with self.lock:
            st = self._inst[inst]
            if st.feed_ms is None:
                return None
            inc = self.tracker.current(inst)
            t = (st.feed_ms - inc.start_ms) / 1000 if inc else 0.0
            return {"type": "clock", "t_s": round(max(t, 0.0), 3),
                    "ts": iso_z(_ms_to_dt(st.feed_ms)), "speed": st.rate,
                    "playing": self._active(st), "seeked": False}  # fmt: skip

    def catch_up(self, inst: str) -> list[dict]:
        """``hello``, the current incident's last 120 s and its latest results."""
        with self.lock:
            st = self._inst[inst]
            return [self.hello(inst), *(m for _, m in st.recent), *st.results]

    def reset(self) -> None:
        """Forget every live incident and feed time (the store and vectors are reset by the
        caller); subscribers get a ``seeked`` clock and an empty ``hello``."""
        with self.lock:
            self.tracker.forget()
            self._points.clear()
            self._snap_n.clear()
            self._feat.clear()
            for inst, st in list(self._inst.items()):
                st.recent.clear()
                st.results = []
                st.trace = None
                self._emit(inst, {"type": "clock", "t_s": 0.0,
                                  "ts": iso_z(_ms_to_dt(st.feed_ms or 0)), "speed": st.rate,
                                  "playing": False, "seeked": True}, keep=False)  # fmt: skip
                st.feed_ms, st.heard_ms, st.wall = None, None, 0.0
                self._emit(inst, self.hello(inst), keep=False)

    def trace(self, inst: str) -> dict | None:
        """The latest live ``matcher_trace`` message at an installation (None before any)."""
        with self.lock:
            return self._inst[inst].trace if inst in self._inst else None

    def feed_state(self) -> dict[str, dict]:
        with self.lock:
            return {i: {"feed_ts": iso_z(_ms_to_dt(st.feed_ms)) if st.feed_ms else None,
                        "rate": st.rate, "active": self._active(st)}
                    for i, st in self._inst.items() if st.feed_ms is not None}  # fmt: skip

    def states(self) -> dict[str, tuple[str, int]]:
        """Incident -> (state, reruns) for the incidents this hub has seen."""
        with self.lock:
            return {i: (inc.state, inc.reruns) for i, inc in self.tracker.incidents.items()}
